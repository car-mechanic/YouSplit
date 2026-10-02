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

    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="shared_list", cascade="all, delete-orphan"
    )
    # Gelernte Kategorie-Regeln der Liste (Roadmap 4.0 #3). Wie expenses an die
    # Liste gebunden: cascade-delete, damit Regeln mit der Liste verschwinden.
    category_rules: Mapped[list["CategoryRule"]] = relationship(
        back_populates="shared_list", cascade="all, delete-orphan"
    )
    # Status der asynchronen Bon-Scans (Bugfix 2026-09-25). Ebenfalls an die
    # Liste gebunden und mit ihr geloescht.
    receipt_jobs: Mapped[list["ReceiptJob"]] = relationship(
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
    # Fallback herangezogen (Altdaten + gescannte Bons ohne feine Aufteilung);
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
    # Bon-Datum (nur beim Scan gesetzt): das von der KI gelesene Kaufdatum.
    # Traegt die Duplikats-Pruefung, damit derselbe Bon auch an einem anderen
    # Tag als Duplikat erkannt wird. Bei manuellen Eintraegen NULL — dort greift
    # als Datum ersatzweise created_at.
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


class ReceiptJob(Base):
    """Status eines asynchron verarbeiteten Bon-Scans ("Fire & Forget").

    Hintergrund (Bugfix 2026-09-25): Seit dem asynchronen Upload (Roadmap 4.0 #2)
    bekam das Frontend nur ``202`` zurueck. Scheiterte die Verarbeitung im
    Hintergrund (z. B. ``404 model not found``), fehlte die Ausgabe einfach —
    ohne jede Rueckmeldung. Jeder Upload legt jetzt einen Job an, den das
    Frontend abfragt (Polling):

    - ``processing``: laeuft (``detail`` traegt optional einen Fortschritts-
      Hinweis, z. B. "KI-Modell wird heruntergeladen").
    - ``done``: Ausgabe angelegt (``expense_id``) → Frontend laedt die Liste neu
      und quittiert den Job (DELETE).
    - ``failed``: ``error`` enthaelt eine nutzerverstaendliche Ursache; bleibt
      sichtbar, bis der Nutzer sie verwirft (DELETE).

    Neue Tabelle → ``create_all`` legt sie beim Backend-Start automatisch an.
    """

    __tablename__ = "receipt_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    list_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shared_lists.id"))
    payer_name: Mapped[str] = mapped_column(String(100))
    # Original-Dateiname, damit der Nutzer fehlgeschlagene Bons zuordnen kann
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="processing")
    detail: Mapped[str | None] = mapped_column(String(300), nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Bewusst ohne FK: wird die Ausgabe spaeter geloescht, bleibt der Job gueltig
    expense_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    shared_list: Mapped["SharedList"] = relationship(back_populates="receipt_jobs")
