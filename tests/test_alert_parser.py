from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SCRIPT = (
    ROOT
    / "scripts"
    / "actualizar_alertas_smn.py"
)

spec = importlib.util.spec_from_file_location(
    "actualizar_alertas_smn",
    SCRIPT,
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class AlertParserTests(unittest.TestCase):
    def test_extract_token(self) -> None:
        token = (
            "eyJhbGciOiJIUzI1NiJ9."
            "eyJzdWIiOiJhbGVydHMifQ."
            "abcdefghijklmnopqrstuvwxyz0123456789"
        )

        html = (
            "<script>"
            f"localStorage.setItem('token','{token}');"
            "</script>"
        )

        self.assertEqual(
            module.extract_token(html),
            token,
        )

    def test_build_active_alert(self) -> None:
        value = [
            {
                "area_id": 759,
                "updated": "2026-07-02T03:00:00Z",
                "reports": [],
                "warnings": [
                    {
                        "date": "2026-07-02",
                        "max_level": 3,
                        "events": [
                            {
                                "id": 41,
                                "max_level": 3,
                            }
                        ],
                    }
                ],
            }
        ]

        result = module.build_alert_file(
            value,
            levels={
                "3": "Amarillo",
                "4": "Naranja",
                "5": "Rojo",
            },
            phenomena={
                "41": "Tormenta",
            },
        )

        self.assertEqual(
            result["active_count"],
            1,
        )
        self.assertEqual(
            result["affected_area_count"],
            1,
        )
        self.assertEqual(
            result["max_level"],
            3,
        )
        self.assertEqual(
            result["alerts"][0]["events"][0]["name"],
            "Tormenta",
        )

    def test_levels_below_three_are_ignored(self) -> None:
        value = [
            {
                "area_id": 100,
                "warnings": [
                    {
                        "date": "2026-07-02",
                        "max_level": 2,
                        "events": [],
                    }
                ],
            }
        ]

        result = module.build_alert_file(
            value,
            levels={},
            phenomena={},
        )

        self.assertEqual(
            result["active_count"],
            0,
        )

    def test_generated_timestamps_do_not_count_as_alert_changes(self) -> None:
        existing = {
            "generated_at": "2026-07-02T01:00:00-03:00",
            "last_success_at": "2026-07-02T01:00:00-03:00",
            "status": "sin_alertas",
            "alerts": [],
        }
        new_value = {
            "generated_at": "2026-07-02T01:05:00-03:00",
            "last_success_at": "2026-07-02T01:05:00-03:00",
            "status": "sin_alertas",
            "alerts": [],
        }

        self.assertFalse(
            module.should_write_alerts(existing, new_value)
        )


if __name__ == "__main__":
    unittest.main()
