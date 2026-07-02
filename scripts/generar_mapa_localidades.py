#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from common import (
    read_json,
    sha256_file,
    write_json_atomic,
)


LOCALITIES_PATH = Path("docs/localidades.min.json")
AREAS_PATH = Path("data/areas_alerta.geojson")
OUTPUT_PATH = Path("docs/localidades_alerta.min.json")
DIAGNOSTIC_PATH = Path(
    "data/diagnostico_localidades_alerta.json"
)
METADATA_PATH = Path("data/mapeo_metadata.json")

ARGENTINA_TZ = ZoneInfo(
    "America/Argentina/Buenos_Aires"
)
EPSILON = 1e-9
GRID_SIZE = 1.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Relacionar las localidades con las áreas de alerta."
        )
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerar aunque las entradas no hayan cambiado.",
    )
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(ARGENTINA_TZ).isoformat(
        timespec="seconds"
    )


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    return result if math.isfinite(result) else None


def load_localities(value: Any) -> list[dict[str, Any]]:
    if (
        isinstance(value, dict)
        and isinstance(value.get("columns"), list)
        and isinstance(value.get("records"), list)
    ):
        columns = [
            str(column)
            for column in value["columns"]
        ]
        result: list[dict[str, Any]] = []

        for record in value["records"]:
            if not isinstance(record, list):
                continue
            result.append(
                {
                    column: (
                        record[index]
                        if index < len(record)
                        else None
                    )
                    for index, column in enumerate(columns)
                }
            )

        return result

    if (
        isinstance(value, dict)
        and isinstance(value.get("localities"), list)
    ):
        return [
            item
            for item in value["localities"]
            if isinstance(item, dict)
        ]

    if isinstance(value, list):
        return [
            item for item in value
            if isinstance(item, dict)
        ]

    raise RuntimeError(
        "El catálogo de localidades tiene una "
        "estructura desconocida."
    )


def point_on_segment(
    x: float,
    y: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> bool:
    cross = (y - y1) * (x2 - x1) - (
        x - x1
    ) * (y2 - y1)

    if abs(cross) > EPSILON:
        return False

    return (
        min(x1, x2) - EPSILON
        <= x
        <= max(x1, x2) + EPSILON
        and min(y1, y2) - EPSILON
        <= y
        <= max(y1, y2) + EPSILON
    )


def point_in_ring(
    x: float,
    y: float,
    ring: list[Any],
) -> bool:
    if len(ring) < 3:
        return False

    inside = False
    previous = ring[-1]

    for current in ring:
        try:
            x1, y1 = float(current[0]), float(current[1])
            x2, y2 = (
                float(previous[0]),
                float(previous[1]),
            )
        except (TypeError, ValueError, IndexError):
            previous = current
            continue

        if point_on_segment(
            x, y, x1, y1, x2, y2
        ):
            return True

        crosses = (y1 > y) != (y2 > y)
        if crosses:
            intersection_x = (
                (x2 - x1)
                * (y - y1)
                / (y2 - y1)
                + x1
            )
            if x < intersection_x:
                inside = not inside

        previous = current

    return inside


def point_in_polygon(
    x: float,
    y: float,
    polygon: list[Any],
) -> bool:
    if not polygon:
        return False

    outer = polygon[0]
    if not isinstance(outer, list):
        return False
    if not point_in_ring(x, y, outer):
        return False

    for hole in polygon[1:]:
        if (
            isinstance(hole, list)
            and point_in_ring(x, y, hole)
        ):
            return False

    return True


def point_in_geometry(
    x: float,
    y: float,
    geometry: dict[str, Any],
) -> bool:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if (
        geometry_type == "Polygon"
        and isinstance(coordinates, list)
    ):
        return point_in_polygon(
            x,
            y,
            coordinates,
        )

    if (
        geometry_type == "MultiPolygon"
        and isinstance(coordinates, list)
    ):
        return any(
            point_in_polygon(x, y, polygon)
            for polygon in coordinates
            if isinstance(polygon, list)
        )

    return False


def iterate_coordinate_pairs(
    value: Any,
) -> Iterable[tuple[float, float]]:
    if (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        yield float(value[0]), float(value[1])
        return

    if isinstance(value, list):
        for item in value:
            yield from iterate_coordinate_pairs(item)


def geometry_bounds(
    geometry: dict[str, Any],
) -> tuple[float, float, float, float]:
    pairs = list(
        iterate_coordinate_pairs(
            geometry.get("coordinates")
        )
    )

    if not pairs:
        raise ValueError("Geometría sin coordenadas.")

    xs = [pair[0] for pair in pairs]
    ys = [pair[1] for pair in pairs]

    return min(xs), min(ys), max(xs), max(ys)


def inside_bounds(
    x: float,
    y: float,
    bounds: tuple[float, float, float, float],
    margin: float = 0.0,
) -> bool:
    min_x, min_y, max_x, max_y = bounds

    return (
        min_x - margin - EPSILON
        <= x
        <= max_x + margin + EPSILON
        and min_y - margin - EPSILON
        <= y
        <= max_y + margin + EPSILON
    )


def point_segment_distance(
    x: float,
    y: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> float:
    dx = x2 - x1
    dy = y2 - y1

    if abs(dx) <= EPSILON and abs(dy) <= EPSILON:
        return math.hypot(x - x1, y - y1)

    proportion = (
        (x - x1) * dx + (y - y1) * dy
    ) / (dx * dx + dy * dy)

    proportion = max(0.0, min(1.0, proportion))

    nearest_x = x1 + proportion * dx
    nearest_y = y1 + proportion * dy

    return math.hypot(
        x - nearest_x,
        y - nearest_y,
    )


def ring_distance(
    x: float,
    y: float,
    ring: list[Any],
) -> float:
    if len(ring) < 2:
        return float("inf")

    distance = float("inf")
    previous = ring[-1]

    for current in ring:
        try:
            distance = min(
                distance,
                point_segment_distance(
                    x,
                    y,
                    float(previous[0]),
                    float(previous[1]),
                    float(current[0]),
                    float(current[1]),
                ),
            )
        except (
            TypeError,
            ValueError,
            IndexError,
        ):
            pass

        previous = current

    return distance


def polygon_distance(
    x: float,
    y: float,
    polygon: list[Any],
) -> float:
    return min(
        (
            ring_distance(x, y, ring)
            for ring in polygon
            if isinstance(ring, list)
        ),
        default=float("inf"),
    )


def geometry_distance(
    x: float,
    y: float,
    geometry: dict[str, Any],
) -> float:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")

    if (
        geometry_type == "Polygon"
        and isinstance(coordinates, list)
    ):
        return polygon_distance(
            x,
            y,
            coordinates,
        )

    if (
        geometry_type == "MultiPolygon"
        and isinstance(coordinates, list)
    ):
        return min(
            (
                polygon_distance(x, y, polygon)
                for polygon in coordinates
                if isinstance(polygon, list)
            ),
            default=float("inf"),
        )

    return float("inf")


def cell_range(
    minimum: float,
    maximum: float,
) -> range:
    return range(
        math.floor(minimum / GRID_SIZE),
        math.floor(maximum / GRID_SIZE) + 1,
    )


def prepare_areas(
    geojson: Any,
) -> tuple[
    list[
        tuple[
            int,
            dict[str, Any],
            tuple[float, float, float, float],
        ]
    ],
    dict[tuple[int, int], list[int]],
]:
    features = (
        geojson.get("features")
        if isinstance(geojson, dict)
        else None
    )

    if not isinstance(features, list):
        raise RuntimeError(
            "El archivo de áreas no es una "
            "FeatureCollection válida."
        )

    areas = []
    grid: dict[tuple[int, int], list[int]] = {}

    for feature in features:
        if not isinstance(feature, dict):
            continue

        properties = feature.get("properties")
        geometry = feature.get("geometry")

        if not isinstance(properties, dict):
            continue
        if not isinstance(geometry, dict):
            continue

        try:
            area_id = int(
                properties.get("gid")
                or properties.get("area_id")
                or feature.get("id")
            )
            bounds = geometry_bounds(geometry)
        except (TypeError, ValueError):
            continue

        index = len(areas)
        areas.append(
            (
                area_id,
                geometry,
                bounds,
            )
        )

        min_x, min_y, max_x, max_y = bounds

        for grid_x in cell_range(min_x, max_x):
            for grid_y in cell_range(min_y, max_y):
                grid.setdefault(
                    (grid_x, grid_y),
                    [],
                ).append(index)

    if not areas:
        raise RuntimeError(
            "No se encontraron áreas de alerta válidas."
        )

    return areas, grid


def candidate_indexes(
    x: float,
    y: float,
    grid: dict[tuple[int, int], list[int]],
    *,
    include_neighbors: bool,
) -> list[int]:
    center_x = math.floor(x / GRID_SIZE)
    center_y = math.floor(y / GRID_SIZE)
    radius = 1 if include_neighbors else 0
    result: set[int] = set()

    for offset_x in range(-radius, radius + 1):
        for offset_y in range(-radius, radius + 1):
            result.update(
                grid.get(
                    (
                        center_x + offset_x,
                        center_y + offset_y,
                    ),
                    [],
                )
            )

    return sorted(result)


def should_regenerate(
    *,
    force: bool,
    locality_hash: str,
    area_hash: str,
) -> bool:
    if force:
        return True

    if not OUTPUT_PATH.exists():
        return True

    if not METADATA_PATH.exists():
        return True

    try:
        metadata = read_json(METADATA_PATH)
    except Exception:
        return True

    return not (
        metadata.get("localities_sha256")
        == locality_hash
        and metadata.get("areas_sha256")
        == area_hash
    )


def main() -> int:
    args = parse_args()

    locality_hash = sha256_file(LOCALITIES_PATH)
    area_hash = sha256_file(AREAS_PATH)

    if not should_regenerate(
        force=args.force,
        locality_hash=locality_hash,
        area_hash=area_hash,
    ):
        print(
            "El catálogo y los polígonos no cambiaron. "
            "Se conserva el mapeo existente."
        )
        return 0

    config = read_json(Path("config/sources.json"))
    proximity_threshold = float(
        config.get(
            "proximity_threshold_degrees",
            0.005,
        )
    )

    localities = load_localities(
        read_json(LOCALITIES_PATH)
    )
    areas, grid = prepare_areas(
        read_json(AREAS_PATH)
    )

    by_locality_id: dict[str, list[int]] = {}
    unmatched = []
    without_coordinates = []
    multiple_matches = []
    proximity_matches = []

    for index, locality in enumerate(
        localities,
        start=1,
    ):
        try:
            locality_id = int(locality.get("id"))
        except (TypeError, ValueError):
            continue

        latitude = number(locality.get("lat"))
        longitude = number(locality.get("lon"))

        base_summary = {
            "id": locality_id,
            "name": locality.get("name"),
            "department": locality.get("department"),
            "province": locality.get("province"),
            "lat": latitude,
            "lon": longitude,
        }

        if latitude is None or longitude is None:
            by_locality_id[str(locality_id)] = []
            without_coordinates.append(base_summary)
            continue

        matches: list[int] = []

        for area_index in candidate_indexes(
            longitude,
            latitude,
            grid,
            include_neighbors=False,
        ):
            area_id, geometry, bounds = areas[area_index]

            if not inside_bounds(
                longitude,
                latitude,
                bounds,
            ):
                continue

            if point_in_geometry(
                longitude,
                latitude,
                geometry,
            ):
                matches.append(area_id)

        matches = sorted(set(matches))
        match_method = "polygon"
        nearest_distance = None

        if not matches:
            candidates: list[tuple[float, int]] = []

            for area_index in candidate_indexes(
                longitude,
                latitude,
                grid,
                include_neighbors=True,
            ):
                area_id, geometry, bounds = areas[area_index]

                if not inside_bounds(
                    longitude,
                    latitude,
                    bounds,
                    margin=proximity_threshold,
                ):
                    continue

                distance = geometry_distance(
                    longitude,
                    latitude,
                    geometry,
                )

                if distance <= proximity_threshold:
                    candidates.append(
                        (distance, area_id)
                    )

            if candidates:
                candidates.sort()
                nearest_distance, nearest_id = candidates[0]
                matches = [nearest_id]
                match_method = "proximity"

        by_locality_id[str(locality_id)] = matches

        summary = {
            **base_summary,
            "area_ids": matches,
            "match_method": match_method,
        }

        if nearest_distance is not None:
            summary["distance_degrees"] = round(
                nearest_distance,
                8,
            )
            proximity_matches.append(summary.copy())

        if not matches:
            unmatched.append(summary)
        elif len(matches) > 1:
            multiple_matches.append(summary)

        if index % 1000 == 0:
            print(
                f"Procesadas {index}/{len(localities)} localidades."
            )

    matched_count = sum(
        1
        for area_ids in by_locality_id.values()
        if area_ids
    )

    generated_at = now_iso()

    public_output = {
        "schema_version": 1,
        "generated_at": generated_at,
        "status": "ok",
        "source": (
            "Polígonos del mapa público de alertas del "
            "Servicio Meteorológico Nacional"
        ),
        "counts": {
            "areas": len(areas),
            "localities": len(localities),
            "matched": matched_count,
            "unmatched": len(unmatched),
            "without_coordinates": len(
                without_coordinates
            ),
            "multiple_matches": len(
                multiple_matches
            ),
            "proximity_matches": len(
                proximity_matches
            ),
        },
        "proximity_threshold_degrees": (
            proximity_threshold
        ),
        "by_locality_id": by_locality_id,
    }

    diagnostics = {
        **public_output,
        "unmatched_localities": unmatched,
        "without_coordinates": without_coordinates,
        "multiple_matches": multiple_matches,
        "proximity_matches": proximity_matches,
    }

    metadata = {
        "schema_version": 1,
        "generated_at": generated_at,
        "localities_sha256": locality_hash,
        "areas_sha256": area_hash,
        "locality_count": len(localities),
        "area_count": len(areas),
    }

    write_json_atomic(
        OUTPUT_PATH,
        public_output,
        compact=True,
    )
    write_json_atomic(
        DIAGNOSTIC_PATH,
        diagnostics,
    )
    write_json_atomic(
        METADATA_PATH,
        metadata,
    )

    print("Relación localidad → área generada.")
    print(f"Áreas: {len(areas)}")
    print(f"Localidades: {len(localities)}")
    print(f"Con área: {matched_count}")
    print(f"Sin área: {len(unmatched)}")
    print(
        "Por proximidad: "
        f"{len(proximity_matches)}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
