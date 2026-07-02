#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import requests

from common import read_json, write_json_atomic


CONFIG_PATH = Path("config/sources.json")
DATA_PATH = Path("data/areas_alerta.geojson")
PUBLIC_PATH = Path("docs/areas_alerta.geojson")

HEADERS = {
    "Accept": "application/geo+json,application/json,text/plain,*/*",
    "User-Agent": "ClimateProyectar-Alerts/1.0",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sincronizar polígonos de áreas de alerta."
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Volver a consultar aunque el archivo local sea válido.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=45.0,
    )
    return parser.parse_args()


def validate_geojson(
    value: Any,
    minimum_area_count: int,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError("El GeoJSON no es un objeto.")

    if value.get("type") != "FeatureCollection":
        raise RuntimeError("El archivo no es una FeatureCollection.")

    features = value.get("features")
    if not isinstance(features, list):
        raise RuntimeError("El GeoJSON no contiene features.")

    valid_features = []
    area_ids: set[int] = set()

    for feature in features:
        if not isinstance(feature, dict):
            continue

        properties = feature.get("properties")
        geometry = feature.get("geometry")

        if not isinstance(properties, dict):
            continue
        if not isinstance(geometry, dict):
            continue
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            continue

        try:
            area_id = int(
                properties.get("gid")
                or properties.get("area_id")
                or feature.get("id")
            )
        except (TypeError, ValueError):
            continue

        if area_id in area_ids:
            continue

        copied = dict(feature)
        copied["properties"] = {
            **properties,
            "gid": area_id,
        }

        valid_features.append(copied)
        area_ids.add(area_id)

    if len(valid_features) < minimum_area_count:
        raise RuntimeError(
            "Se esperaban al menos "
            f"{minimum_area_count} áreas y se encontraron "
            f"{len(valid_features)}."
        )

    valid_features.sort(
        key=lambda feature: int(feature["properties"]["gid"])
    )

    return {
        "type": "FeatureCollection",
        "features": valid_features,
    }


def local_file_is_valid(minimum_area_count: int) -> bool:
    if not DATA_PATH.exists():
        return False

    try:
        value = read_json(DATA_PATH)
        validate_geojson(value, minimum_area_count)
        return True
    except Exception:
        return False


def download_geojson(
    urls: list[str],
    minimum_area_count: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    session = requests.Session()
    errors: list[str] = []

    for url in urls:
        try:
            response = session.get(
                url,
                headers=HEADERS,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            value = response.json()
            validated = validate_geojson(
                value,
                minimum_area_count,
            )
            print(
                f"Polígonos obtenidos desde {url}: "
                f"{len(validated['features'])} áreas."
            )
            return validated
        except Exception as error:
            errors.append(f"{url}: {error}")

    raise RuntimeError(
        "No se pudo descargar un GeoJSON válido. "
        + " | ".join(errors)
    )


def main() -> int:
    args = parse_args()
    config = read_json(CONFIG_PATH)

    minimum_area_count = int(
        config.get("expected_minimum_area_count", 150)
    )

    if not args.refresh and local_file_is_valid(
        minimum_area_count
    ):
        value = validate_geojson(
            read_json(DATA_PATH),
            minimum_area_count,
        )

        # Ensure the public copy exists and is synchronized.
        write_json_atomic(
            PUBLIC_PATH,
            value,
            compact=True,
        )

        print(
            "Los polígonos locales ya son válidos: "
            f"{len(value['features'])} áreas."
        )
        return 0

    urls = [
        str(url)
        for url in config.get(
            "alert_areas_bootstrap_urls",
            [],
        )
        if isinstance(url, str) and url
    ]

    if not urls:
        raise RuntimeError(
            "No hay fuentes configuradas para los polígonos."
        )

    value = download_geojson(
        urls,
        minimum_area_count,
        args.timeout_seconds,
    )

    write_json_atomic(
        DATA_PATH,
        value,
        compact=True,
    )
    write_json_atomic(
        PUBLIC_PATH,
        value,
        compact=True,
    )

    print("Polígonos guardados en data/ y docs/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
