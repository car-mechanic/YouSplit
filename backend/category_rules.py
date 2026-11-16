"""Remembered merchants for the bank statement import ("Haendler merken").

A rule maps a recipient keyword of one list to a category, e.g. "Hans Meier
e.K." -> "Lebensmittel". ``bank_statement.classify`` applies the rules before
the merchant list and the owner-market heuristic, so a rule is how a user fixes
what no fixed list can cover: owner names and false hits.

The import only distinguishes groceries from everything else (it creates
grocery expenses), so a rule can express exactly two things: "this is food" or
"this is not food, ignore it". Any finer category would have no effect.

Kept free of FastAPI so the logic stays testable; the router only maps
``RuleError`` to HTTP status codes.
"""

import logging
import uuid

from sqlalchemy.orm import Session

import bank_statement
import models

logger = logging.getLogger("yousplit.category_rules")

CATEGORY_FOOD = bank_statement.CATEGORY_FOOD
# Marker for "not groceries": a rule hit with any category other than food
# makes the booking non-food, so this needs no special case in ``classify``.
CATEGORY_IGNORE = "Ignorieren"
RULE_CATEGORIES = (CATEGORY_FOOD, CATEGORY_IGNORE)

# Shorter keywords would hit far too many bookings ("EK", "AG", "DM" as part
# of unrelated text). Only letters and digits of the folded form count, so
# "e.K." is too short as well.
MIN_KEYWORD_LENGTH = 3
# Upper bound per list against abuse; real lists need a few dozen at most.
MAX_RULES_PER_LIST = 500


class RuleError(Exception):
    """A rule request was rejected; ``status_code`` is the HTTP equivalent."""

    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


def normalize_keyword(raw: str) -> str:
    """Trim the keyword and collapse inner whitespace.

    The keyword is stored as typed (minus whitespace) so the overview shows
    "Hans Meier e.K." instead of the folded "HANS MEIER E K". Matching always
    uses the folded form anyway.
    """
    keyword = " ".join(raw.split())
    letters = bank_statement.fold_keyword(keyword).replace(" ", "")
    if len(letters) < MIN_KEYWORD_LENGTH:
        raise RuleError(
            f"Das Stichwort muss mindestens {MIN_KEYWORD_LENGTH} Buchstaben "
            "oder Ziffern lang sein."
        )
    return keyword


def validate_category(category: str) -> str:
    if category not in RULE_CATEGORIES:
        raise RuleError(
            f"Unbekannte Kategorie '{category}' (erlaubt: "
            f"{', '.join(RULE_CATEGORIES)})."
        )
    return category


def list_rules(db: Session, list_id: uuid.UUID) -> list[models.CategoryRule]:
    """All rules of a list, sorted by keyword for a stable overview."""
    rules = (
        db.query(models.CategoryRule)
        .filter(models.CategoryRule.list_id == list_id)
        .all()
    )
    return sorted(rules, key=lambda rule: rule.recipient_keyword.casefold())


def rule_pairs(db: Session, list_id: uuid.UUID) -> list[tuple[str, str]]:
    """Rules in the ``(keyword, category)`` form ``classify`` expects."""
    return [
        (rule.recipient_keyword, rule.category) for rule in list_rules(db, list_id)
    ]


def upsert_rule(
    db: Session, list_id: uuid.UUID, raw_keyword: str, category: str
) -> tuple[models.CategoryRule, bool]:
    """Create a rule or update the existing one with the same folded keyword.

    "Hans Meier e.K." and "HANS MEIER E K" fold to the same key and match the
    same bookings, so two rules for them could only contradict each other.
    Returns the rule and whether it was newly created.

    Two concurrent POSTs with the same keyword can both miss the lookup and
    create a duplicate. That is accepted on purpose: duplicates match the same
    bookings, the next save of that keyword updates one of them and the user
    can delete the other. A unique constraint would need the folded keyword
    as a stored column (no migrations here) for a race that hardly happens.
    """
    keyword = normalize_keyword(raw_keyword)
    category = validate_category(category)
    key = bank_statement.fold_keyword(keyword)

    existing = list_rules(db, list_id)
    for rule in existing:
        if bank_statement.fold_keyword(rule.recipient_keyword) == key:
            rule.recipient_keyword = keyword
            rule.category = category
            db.commit()
            db.refresh(rule)
            logger.info("Rule updated (list %s): %r -> %s", list_id, keyword, category)
            return rule, False

    if len(existing) >= MAX_RULES_PER_LIST:
        raise RuleError(
            f"Es können höchstens {MAX_RULES_PER_LIST} Händler gemerkt werden.",
            status_code=409,
        )
    rule = models.CategoryRule(
        list_id=list_id, recipient_keyword=keyword, category=category
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    logger.info("Rule created (list %s): %r -> %s", list_id, keyword, category)
    return rule, True


def delete_rule(db: Session, list_id: uuid.UUID, rule_id: uuid.UUID) -> None:
    """Delete a rule; a rule of another list counts as not found."""
    rule = db.get(models.CategoryRule, rule_id)
    if rule is None or rule.list_id != list_id:
        raise RuleError("Gemerkter Händler nicht gefunden.", status_code=404)
    db.delete(rule)
    db.commit()
    logger.info("Rule deleted (list %s): %r", list_id, rule.recipient_keyword)
