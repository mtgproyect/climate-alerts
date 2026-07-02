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
    / "generar_mapa_localidades.py"
)

spec = importlib.util.spec_from_file_location(
    "generar_mapa_localidades",
    SCRIPT,
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class GeometryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.square = [
            [
                [0.0, 0.0],
                [10.0, 0.0],
                [10.0, 10.0],
                [0.0, 10.0],
                [0.0, 0.0],
            ]
        ]

    def test_point_inside_polygon(self) -> None:
        self.assertTrue(
            module.point_in_polygon(
                5.0,
                5.0,
                self.square,
            )
        )

    def test_point_outside_polygon(self) -> None:
        self.assertFalse(
            module.point_in_polygon(
                20.0,
                5.0,
                self.square,
            )
        )

    def test_point_on_boundary_is_included(self) -> None:
        self.assertTrue(
            module.point_in_polygon(
                0.0,
                5.0,
                self.square,
            )
        )

    def test_hole_is_excluded(self) -> None:
        polygon = [
            self.square[0],
            [
                [4.0, 4.0],
                [6.0, 4.0],
                [6.0, 6.0],
                [4.0, 6.0],
                [4.0, 4.0],
            ],
        ]

        self.assertFalse(
            module.point_in_polygon(
                5.0,
                5.0,
                polygon,
            )
        )

    def test_distance_to_polygon(self) -> None:
        distance = module.polygon_distance(
            10.2,
            5.0,
            self.square,
        )
        self.assertAlmostEqual(
            distance,
            0.2,
            places=7,
        )


if __name__ == "__main__":
    unittest.main()
