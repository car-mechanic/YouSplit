import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class SharedList(Base):
    """Eine geteilte Ausgabenliste. Die ``id`` (UUID) ist zugleich der Share-Link
    — wer sie kennt, sieht die Liste (kein Login)."""

    __tablename__ = "shared_lists"

    # Mapped[uuid.UUID] wird auf Postgres automatisch eine native UUID-Spalte
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Personen der Liste (Namen, Reihenfolge wie eingegeben; 2026-10-08). Werden
    # im Tutorial einer neuen Liste festgelegt, damit schon die erste Ausgabe
    # auf alle aufgeteilt wird, statt erst 100 %, dann 50/50, dann Drittel.
    # NULL bei Altlisten = nur die Personen aus den Ausgaben.
    # Nachtraeglich ergaenzte Spalte → ``database.ensure_schema_updates``.
    members: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, default=None
    )

    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="shared_list", cascade="all, delete-orphan"
    )
    # Gelernte Kategorie-Regeln der Liste (Roadmap 4.0 #3). Wie expenses an die
    # Liste gebunden: cascade-delete, damit Regeln mit der Liste verschwinden.
    category_rules: Mapped[list["CategoryRule"]] = relationship(
        back_populates="shared_list", cascade="all, delete-orphan"
    )


class Expense(Base):
    """Eine einzelne Ausgabe innerhalb einer Liste (Zahler, Betrag, Aufteilung)."""

    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    list_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shared_lists.id"))
    title: Mapped[str] = mapped_column(String(200))
    amount: Mapped[float]
    payer_name: Mapped[str] = mapped_column(String(100))
    # Gewichtung der Aufteilung: 0.5 = 50/50, 0.7 = 70/30. Wird nur noch als
    # Fallback herangezogen (Altdaten ohne feine Aufteilung);
    # die maßgebliche Pro-Person-Aufteilung steht in ``splits`` (siehe unten).
    split_ratio: Mapped[float] = mapped_column(default=0.5)
    # Advanced Split (Roadmap 3.0 #3): explizite Pro-Person-Aufteilung als
    # JSON-Objekt {Name: Betrag} — Betraege in der Erfassungswaehrung ``currency``
    # (analog zu ``amount``; EUR-Wert = Betrag * exchange_rate). Die Summe ergibt
    # exakt ``amount`` (das Frontend garantiert das ueber die 1-Cent-Verteilung).
    # NULL = keine feine Aufteilung hinterlegt → der Kassensturz faellt auf
    # ``split_ratio`` (Rest gleichmaessig auf die anderen) zurueck.
    splits: Mapped[dict[str, float] | None] = mapped_column(
        JSON, nullable=True, default=None
    )
    category: Mapped[str] = mapped_column(String(100), default="Unknown/Manuell")
    # Anlagezeitpunkt: fuer Sortierung ("neueste zuerst") und die
    # Duplikats-Pruefung (gleicher Betrag am selben Tag)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Ausgabedatum (Datum auf dem Bon bzw. der Buchung). Traegt die
    # Duplikats-Pruefung. Bei Altdaten NULL — dort greift als Datum ersatzweise
    # created_at.
    receipt_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Multi-Currency (Roadmap 2.0 #3): Erfassungswaehrung der Ausgabe und der
    # zugehoerige Tageskurs. Konvention: exchange_rate = EUR-Wert einer Einheit
    # von currency, der EUR-Betrag ist also amount * exchange_rate. Fuer EUR ist
    # der Kurs 1.0. server_default sorgt dafuer, dass die Spalten auch beim
    # nachtraeglichen ALTER auf einer laufenden DB einen Wert haben.
    currency: Mapped[str] = mapped_column(
        String(3), default="EUR", server_default="EUR"
    )
    exchange_rate: Mapped[float] = mapped_column(
        default=1.0, server_default=text("1.0")
    )

    shared_list: Mapped["SharedList"] = relationship(back_populates="expenses")


class CategoryRule(Base):
    """Gelernte Zuordnung "Empfaenger-Stichwort -> Kategorie" je Liste.

    Fundament fuer den Kontoauszug-Import (Roadmap 4.0 #3): Beim Parsen eines
    Kontoauszugs merkt sich das System hier, welche Kategorie ein Nutzer einem
    Empfaenger (z. B. ``recipient_keyword="REWE"`` -> ``category="Lebensmittel"``)
    zugewiesen hat, um kuenftige Buchungen desselben Empfaengers automatisch
    einzuordnen ("Smart Memory"). Die eigentliche Anwendungslogik folgt in einem
    spaeteren Schritt des Epics — dies legt nur das Schema an.
    """

    __tablename__ = "category_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    list_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shared_lists.id"))
    # Stichwort aus dem Verwendungszweck/Empfaenger (case-insensitive gedacht),
    # z. B. "REWE", "AMAZON", "DB VERTRIEB".
    recipient_keyword: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(100))

    shared_list: Mapped["SharedList"] = relationship(
        back_populates="category_rules"
    )
