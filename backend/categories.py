"""Standard-Kategorien der Ausgaben (eine Wahrheit fuer Bon-KI und Frontend).

Spiegel von ``frontend/src/categories.ts``. Nutzer koennen im Frontend eigene
Kategorien anlegen; sie stehen dann nur an der Ausgabe (``Expense.category``),
eine eigene Tabelle gibt es dafuer nicht.
"""

DEFAULT_CATEGORIES = (
    "Lebensmittel",
    "Auswärtsessen",
    "Haushalt",
    "Drogerie",
    "Freizeit",
    "Mobilität",
    "Sonstiges",
)

# Auffang-Kategorie, wenn die Bon-KI nichts Passendes liefert
FALLBACK_CATEGORY = "Sonstiges"

# Fruehere Kategorie-Namen (bis 2026-10-08), die das Modell noch liefern koennte
LEGACY_ALIASES = {"Restaurant": "Auswärtsessen", "Kosmetik": "Drogerie"}
