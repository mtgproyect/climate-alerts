#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

from common import (
    meaningful_json_signature,
    read_json,
    write_json_atomic,
)


CONFIG_PATH = Path("config/sources.json")
PHENOMENA_PATH = Path("config/fenomenos.json")
ALERTS_PATH = Path("docs/alertas.json")
MANIFEST_PATH = Path("docs/manifiesto.json")
MAPPING_PATH = Path(
    "docs/localidades_alerta.min.json"
)
AREAS_PATH = Path("data/areas_alerta.geojson")

ARGENTINA_TZ = ZoneInfo(
    "America/Argentina/Buenos_Aires"
)

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
}

TRANSIENT_STATUS = {
    408,
    425,
    429,
    500,
    502,
    503,
    504,
}


class TokenRejected(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Actualizar alertas oficiales del SMN."
    )
    parser.add_argument(
        "--http-attempts",
        type=int,
        default=4,
    )
    parser.add_argument(
        "--retry-base-seconds",
        type=float,
        default=2.0,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=45.0,
    )
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(ARGENTINA_TZ).isoformat(
        timespec="seconds"
    )


def to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def request_with_retry(
    session: requests.Session,
    url: str,
    *,
    headers: dict[str, str],
    attempts: int,
    retry_base_seconds: float,
    timeout_seconds: float,
) -> requests.Response:
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            response = session.get(
                url,
                headers=headers,
                timeout=timeout_seconds,
            )

            if response.status_code in TRANSIENT_STATUS:
                raise requests.HTTPError(
                    (
                        "Respuesta temporal "
                        f"HTTP {response.status_code}"
                    ),
                    response=response,
                )

            return response

        except requests.RequestException as error:
            last_error = error

            if attempt >= attempts:
                break

            wait_seconds = (
                retry_base_seconds
                * (2 ** (attempt - 1))
            )

            print(
                f"Reintento {attempt}/{attempts} "
                f"en {wait_seconds:.1f} s: {error}"
            )
            time.sleep(wait_seconds)

    raise RuntimeError(
        f"No se pudo consultar {url}: {last_error}"
    )


def extract_token(html: str) -> str | None:
    patterns = (
        (
            r"localStorage\.setItem\(\s*[\"']token[\"']"
            r"\s*,\s*[\"']([^\"']+)[\"']\s*\)"
        ),
        (
            r"localStorage\.setItem\(\s*`token`"
            r"\s*,\s*`([^`]+)`\s*\)"
        ),
        r"[\"']token[\"']\s*:\s*[\"']([^\"']+)[\"']",
        (
            r"(eyJ[A-Za-z0-9_-]+\."
            r"[A-Za-z0-9_-]+\."
            r"[A-Za-z0-9_-]+)"
        ),
    )

    for pattern in patterns:
        match = re.search(pattern, html)
        if not match:
            continue

        token = match.group(1).strip()

        if token.count(".") == 2 and len(token) > 40:
            return token

    return None


def get_token(
    session: requests.Session,
    token_pages: list[str],
    *,
    attempts: int,
    retry_base_seconds: float,
    timeout_seconds: float,
) -> str:
    errors: list[str] = []

    for page_url in token_pages:
        try:
            response = request_with_retry(
                session,
                page_url,
                headers={
                    **BASE_HEADERS,
                    "Accept": (
                        "text/html,"
                        "application/xhtml+xml"
                    ),
                },
                attempts=attempts,
                retry_base_seconds=(
                    retry_base_seconds
                ),
                timeout_seconds=timeout_seconds,
            )
            response.raise_for_status()

            token = extract_token(response.text)
            if token:
                print(
                    "Token temporal obtenido desde "
                    f"{page_url}"
                )
                return token

            errors.append(
                f"{page_url}: token no encontrado"
            )
        except Exception as error:
            errors.append(
                f"{page_url}: {error}"
            )

    raise RuntimeError(
        "No se pudo obtener el token temporal. "
        + " | ".join(errors)
    )


def api_headers(token: str) -> dict[str, str]:
    return {
        **BASE_HEADERS,
        "Accept": "application/json",
        "Authorization": f"JWT {token}",
        "Origin": "https://www.smn.gob.ar",
        "Referer": "https://www.smn.gob.ar/alertas",
    }


def fetch_alert_response(
    session: requests.Session,
    endpoint: str,
    token: str,
    *,
    attempts: int,
    retry_base_seconds: float,
    timeout_seconds: float,
) -> Any:
    response = request_with_retry(
        session,
        endpoint,
        headers=api_headers(token),
        attempts=attempts,
        retry_base_seconds=retry_base_seconds,
        timeout_seconds=timeout_seconds,
    )

    if response.status_code in {401, 403}:
        raise TokenRejected(
            "El endpoint rechazó el token temporal."
        )

    response.raise_for_status()

    try:
        return response.json()
    except ValueError as error:
        raise RuntimeError(
            "La respuesta no contiene JSON válido."
        ) from error


def extract_area_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [
            item for item in value
            if isinstance(item, dict)
        ]

    if isinstance(value, dict):
        for key in (
            "data",
            "areas",
            "results",
            "items",
        ):
            items = value.get(key)

            if isinstance(items, list):
                return [
                    item for item in items
                    if isinstance(item, dict)
                ]

    raise RuntimeError(
        "La respuesta de alertas tiene una "
        "estructura desconocida."
    )


def normalize_event(
    event: dict[str, Any],
    phenomena: dict[str, str],
    levels: dict[str, str],
) -> dict[str, Any] | None:
    event_id = to_int(event.get("id"))
    level = to_int(event.get("max_level"))

    if (
        event_id is None
        or level is None
        or level < 3
    ):
        return None

    return {
        "id": event_id,
        "name": phenomena.get(str(event_id)),
        "level": level,
        "level_name": levels.get(
            str(level),
            f"Nivel {level}",
        ),
    }


def normalize_reports(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def build_alert_file(
    value: Any,
    *,
    levels: dict[str, str],
    phenomena: dict[str, str],
) -> dict[str, Any]:
    areas = extract_area_list(value)

    alerts: list[dict[str, Any]] = []
    affected_area_ids: set[int] = set()
    maximum_level = 1
    smn_updated_at: str | None = None

    for area in areas:
        area_id = to_int(
            area.get("area_id")
            or area.get("gid")
            or area.get("id")
        )

        if area_id is None:
            continue

        updated = area.get("updated")

        if isinstance(updated, str) and updated:
            if (
                smn_updated_at is None
                or updated > smn_updated_at
            ):
                smn_updated_at = updated

        warnings = area.get("warnings")

        if not isinstance(warnings, list):
            continue

        for warning in warnings:
            if not isinstance(warning, dict):
                continue

            declared_level = (
                to_int(warning.get("max_level"))
                or 1
            )

            raw_events = warning.get("events")
            active_events = []

            if isinstance(raw_events, list):
                for raw_event in raw_events:
                    if not isinstance(
                        raw_event,
                        dict,
                    ):
                        continue

                    event = normalize_event(
                        raw_event,
                        phenomena,
                        levels,
                    )

                    if event is not None:
                        active_events.append(event)

            event_level = max(
                (
                    event["level"]
                    for event in active_events
                ),
                default=1,
            )

            level = max(
                declared_level,
                event_level,
            )

            if level < 3:
                continue

            date = warning.get("date")

            alerts.append(
                {
                    "area_id": area_id,
                    "date": (
                        date
                        if isinstance(date, str)
                        else None
                    ),
                    "updated": (
                        updated
                        if isinstance(updated, str)
                        else None
                    ),
                    "level": level,
                    "level_name": levels.get(
                        str(level),
                        f"Nivel {level}",
                    ),
                    "events": active_events,
                    "reports": normalize_reports(
                        area.get("reports")
                    ),
                }
            )

            affected_area_ids.add(area_id)
            maximum_level = max(
                maximum_level,
                level,
            )

    alerts.sort(
        key=lambda alert: (
            alert.get("date") or "",
            -(alert.get("level") or 0),
            alert.get("area_id") or 0,
        )
    )

    timestamp = now_iso()

    return {
        "schema_version": 1,
        "generated_at": timestamp,
        "last_success_at": timestamp,
        "smn_updated_at": smn_updated_at,
        "status": (
            "con_alertas"
            if alerts
            else "sin_alertas"
        ),
        "source": (
            "Servicio Meteorológico Nacional"
        ),
        "source_endpoint": (
            "/v1/warning/alert/area"
            "?mode=alert&compact=true"
        ),
        "area_records_received": len(areas),
        "active_count": len(alerts),
        "affected_area_count": len(
            affected_area_ids
        ),
        "max_level": maximum_level,
        "levels": levels,
        "phenomena": phenomena,
        "alerts": alerts,
    }


def build_manifest(
    alerts: dict[str, Any],
) -> dict[str, Any]:
    mapping = (
        read_json(MAPPING_PATH)
        if MAPPING_PATH.exists()
        else {}
    )
    areas = (
        read_json(AREAS_PATH)
        if AREAS_PATH.exists()
        else {}
    )

    area_features = (
        areas.get("features")
        if isinstance(areas, dict)
        else []
    )

    mapping_counts = (
        mapping.get("counts")
        if isinstance(mapping, dict)
        else {}
    )

    return {
        "schema_version": 1,
        "generated_at": alerts.get(
            "generated_at"
        ),
        "enabled": True,
        "status": alerts.get("status"),
        "source": {
            "name": (
                "Servicio Meteorológico Nacional"
            ),
            "official_page": (
                "https://www.smn.gob.ar/alertas"
            ),
            "endpoint": (
                "https://ws1.smn.gob.ar/"
                "v1/warning/alert/area"
                "?mode=alert&compact=true"
            ),
        },
        "counts": {
            "alert_areas": (
                len(area_features)
                if isinstance(
                    area_features,
                    list,
                )
                else 0
            ),
            "mapped_localities": (
                mapping_counts.get(
                    "matched",
                    0,
                )
            ),
            "total_localities": (
                mapping_counts.get(
                    "localities",
                    10601,
                )
            ),
            "active_alerts": alerts.get(
                "active_count",
                0,
            ),
            "affected_areas": alerts.get(
                "affected_area_count",
                0,
            ),
            "maximum_level": alerts.get(
                "max_level",
                1,
            ),
        },
        "files": {
            "alerts": "alertas.json",
            "locality_mapping": (
                "localidades_alerta.min.json"
            ),
            "areas": "areas_alerta.geojson",
            "localities": "localidades.min.json",
        },
    }


def should_write_alerts(
    existing: dict[str, Any] | None,
    new_value: dict[str, Any],
) -> bool:
    if not existing:
        return True

    ignored = {
        "generated_at",
        "last_success_at",
    }

    return meaningful_json_signature(
        existing,
        ignored,
    ) != meaningful_json_signature(
        new_value,
        ignored,
    )


def main() -> int:
    args = parse_args()
    config = read_json(CONFIG_PATH)
    phenomena_config = read_json(
        PHENOMENA_PATH
    )

    levels = {
        str(key): str(value)
        for key, value in phenomena_config.get(
            "levels",
            {},
        ).items()
    }
    phenomena = {
        str(key): str(value)
        for key, value in phenomena_config.get(
            "phenomena",
            {},
        ).items()
    }

    token_pages = [
        str(url)
        for url in config.get(
            "token_pages",
            [],
        )
        if isinstance(url, str) and url
    ]
    endpoint = str(
        config["alerts_endpoint"]
    )

    session = requests.Session()

    try:
        token = get_token(
            session,
            token_pages,
            attempts=args.http_attempts,
            retry_base_seconds=(
                args.retry_base_seconds
            ),
            timeout_seconds=(
                args.timeout_seconds
            ),
        )

        try:
            response_value = fetch_alert_response(
                session,
                endpoint,
                token,
                attempts=args.http_attempts,
                retry_base_seconds=(
                    args.retry_base_seconds
                ),
                timeout_seconds=(
                    args.timeout_seconds
                ),
            )
        except TokenRejected:
            print(
                "El token fue rechazado. "
                "Solicitando otro."
            )

            token = get_token(
                session,
                token_pages,
                attempts=args.http_attempts,
                retry_base_seconds=(
                    args.retry_base_seconds
                ),
                timeout_seconds=(
                    args.timeout_seconds
                ),
            )

            response_value = fetch_alert_response(
                session,
                endpoint,
                token,
                attempts=args.http_attempts,
                retry_base_seconds=(
                    args.retry_base_seconds
                ),
                timeout_seconds=(
                    args.timeout_seconds
                ),
            )

        alerts = build_alert_file(
            response_value,
            levels=levels,
            phenomena=phenomena,
        )

        existing = None

        if ALERTS_PATH.exists():
            try:
                existing = read_json(
                    ALERTS_PATH
                )
            except Exception:
                existing = None

        alerts_changed = should_write_alerts(
            existing,
            alerts,
        )

        if alerts_changed:
            write_json_atomic(
                ALERTS_PATH,
                alerts,
            )
            print(
                "Se publicaron cambios de alertas."
            )
        else:
            print(
                "Las alertas activas no cambiaron."
            )

        effective_alerts = (
            alerts
            if alerts_changed or not existing
            else existing
        )
        new_manifest = build_manifest(
            effective_alerts
        )

        existing_manifest = None
        if MANIFEST_PATH.exists():
            try:
                existing_manifest = read_json(
                    MANIFEST_PATH
                )
            except Exception:
                existing_manifest = None

        manifest_changed = (
            meaningful_json_signature(
                existing_manifest,
                {"generated_at"},
            )
            != meaningful_json_signature(
                new_manifest,
                {"generated_at"},
            )
        )

        if manifest_changed:
            write_json_atomic(
                MANIFEST_PATH,
                new_manifest,
            )
            print(
                "Se actualizaron los conteos del manifiesto."
            )
        elif not alerts_changed:
            print(
                "No hay archivos públicos nuevos para guardar."
            )

        print(
            "Registros de área recibidos: "
            f"{alerts['area_records_received']}"
        )
        print(
            f"Alertas activas: "
            f"{alerts['active_count']}"
        )
        print(
            f"Áreas afectadas: "
            f"{alerts['affected_area_count']}"
        )
        print(
            f"Nivel máximo: "
            f"{alerts['max_level']}"
        )

        return 0

    except Exception as error:
        print(
            "No se pudieron actualizar "
            f"las alertas: {error}"
        )

        # Preserve the last valid publication.
        if ALERTS_PATH.exists():
            try:
                existing = read_json(
                    ALERTS_PATH
                )

                if (
                    isinstance(existing, dict)
                    and existing.get("status")
                    not in {
                        None,
                        "pending",
                        "sin_datos",
                    }
                ):
                    print(
                        "Se conserva el último "
                        "archivo válido."
                    )
                    return 0
            except Exception:
                pass

        timestamp = now_iso()

        fallback = {
            "schema_version": 1,
            "generated_at": timestamp,
            "last_success_at": None,
            "smn_updated_at": None,
            "status": "sin_datos",
            "source": (
                "Servicio Meteorológico Nacional"
            ),
            "source_endpoint": (
                "/v1/warning/alert/area"
                "?mode=alert&compact=true"
            ),
            "area_records_received": 0,
            "active_count": 0,
            "affected_area_count": 0,
            "max_level": 1,
            "levels": levels,
            "phenomena": phenomena,
            "alerts": [],
            "last_error": str(error),
        }

        write_json_atomic(
            ALERTS_PATH,
            fallback,
        )
        write_json_atomic(
            MANIFEST_PATH,
            build_manifest(fallback),
        )

        return 0


if __name__ == "__main__":
    sys.exit(main())
