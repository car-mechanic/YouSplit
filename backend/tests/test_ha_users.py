"""Tests fuer die Auswahl der Home-Assistant-Benutzer (ha_users.selectable_users).

Ausfuehren (im backend-Ordner):

    python -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ha_users import selectable_users  # noqa: E402


class SelectableUsersTest(unittest.TestCase):
    def test_systembenutzer_und_inaktive_fallen_heraus(self) -> None:
        raw = [
            {"id": "1", "name": "Anna", "is_active": True},
            {"id": "2", "name": "Supervisor", "is_active": True, "system_generated": True},
            {"id": "3", "name": "Gesperrt", "is_active": False},
        ]
        self.assertEqual([u.id for u in selectable_users(raw)], ["1"])

    def test_sortierung_ignoriert_gross_und_kleinschreibung(self) -> None:
        raw = [
            {"id": "1", "name": "zoe", "is_active": True},
            {"id": "2", "name": "Anna", "is_active": True},
            {"id": "3", "name": "bernd", "is_active": True},
        ]
        self.assertEqual([u.name for u in selectable_users(raw)], ["Anna", "bernd", "zoe"])

    def test_name_faellt_auf_benutzername_und_id_zurueck(self) -> None:
        raw = [
            {"id": "1", "name": "", "username": "kev", "is_active": True},
            {"id": "2", "name": None, "is_active": True},
        ]
        names = {u.id: u.name for u in selectable_users(raw)}
        self.assertEqual(names, {"1": "kev", "2": "2"})


if __name__ == "__main__":
    unittest.main()
