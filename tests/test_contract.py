from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AlertContractTests(unittest.TestCase):
    def test_locality_catalog_has_10601_records(self) -> None:
        value = json.loads(
            (
                ROOT
                / "docs"
                / "localidades.min.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(value["count"], 10601)
        self.assertEqual(
            len(value["records"]),
            10601,
        )
        self.assertIn("lat", value["columns"])
        self.assertIn("lon", value["columns"])

    def test_initial_alert_contract(self) -> None:
        value = json.loads(
            (
                ROOT
                / "docs"
                / "alertas.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(value["schema_version"], 1)
        self.assertIn(
            value["status"],
            {
                "pending",
                "con_alertas",
                "sin_alertas",
                "sin_datos",
            },
        )
        self.assertIsInstance(value["alerts"], list)

    def test_mapping_contract(self) -> None:
        value = json.loads(
            (
                ROOT
                / "docs"
                / "localidades_alerta.min.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(value["schema_version"], 1)
        self.assertEqual(
            value["counts"]["localities"],
            10601,
        )
        self.assertIsInstance(
            value["by_locality_id"],
            dict,
        )

    def test_no_private_credentials(self) -> None:
        forbidden = (
            "github" + "_pat_",
            "gh" + "p_",
            "BEGIN " + "PRIVATE KEY",
            "BEGIN RSA " + "PRIVATE KEY",
            "BEGIN OPENSSH " + "PRIVATE KEY",
        )

        text_extensions = {
            ".py",
            ".js",
            ".json",
            ".geojson",
            ".yml",
            ".yaml",
            ".md",
            ".txt",
            ".css",
            ".html",
        }

        current_test = Path(__file__).resolve()

        for path in ROOT.rglob("*"):
            if path.resolve() == current_test:
                continue

            if (
                not path.is_file()
                or path.suffix.lower()
                not in text_extensions
            ):
                continue

            content = path.read_text(
                encoding="utf-8",
                errors="ignore",
            )

            for marker in forbidden:
                self.assertNotIn(
                    marker,
                    content,
                    msg=f"Posible secreto en {path}",
                )


if __name__ == "__main__":
    unittest.main()
