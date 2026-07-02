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
    / "sincronizar_areas_alerta.py"
)

spec = importlib.util.spec_from_file_location(
    "sincronizar_areas_alerta",
    SCRIPT,
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class AreaSyncTests(unittest.TestCase):
    def test_validate_geojson(self) -> None:
        value = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"gid": 1},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [0, 0],
                                [1, 0],
                                [1, 1],
                                [0, 0],
                            ]
                        ],
                    },
                }
            ],
        }

        result = module.validate_geojson(
            value,
            minimum_area_count=1,
        )

        self.assertEqual(
            len(result["features"]),
            1,
        )
        self.assertEqual(
            result["features"][0]["properties"]["gid"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
