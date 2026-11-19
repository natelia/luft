"""Client for the GIOS open air-quality API (https://api.gios.gov.pl).

Contract of this module:
- ``fetch_all`` returns one ``GiosStation`` per station in the country,
  with the latest valid PM2.5/PM10 reading (``None`` when unknown).
- Only a failure of the station *list* raises (``GiosError``).
  Any per-station or per-sensor problem degrades to ``None`` values.
"""

import time
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.config import Settings

PM_CODES = ("PM2.5", "PM10")


class GiosError(RuntimeError):
    """The station list itself could not be fetched."""


@dataclass
class GiosStation:
    """Latest known readings for one GIOS station; None = no valid value."""

    id: int
    name: str
    city: str
    lat: float
    lon: float
    pm25: float | None
    pm10: float | None


def fetch_all(
    settings: Settings | None = None,
    *,
    client: httpx.Client | None = None,
) -> list[GiosStation]:
    """Fetch all stations with their latest PM values (see module docstring)."""
    settings = settings or Settings()
    if client is None:
        client = httpx.Client(timeout=10.0)

    try:
        response = client.get(f"{settings.gios_base_url}/station/findAll")
        response.raise_for_status()
        raw_stations = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise GiosError(f"could not fetch the station list: {exc}") from exc

    snapshot: list[GiosStation] = []
    for raw in raw_stations:
        snapshot.append(_station_with_values(raw, client, settings))
        time.sleep(0.1)  # be polite to the public API between stations
    return snapshot


def _station_with_values(
    raw: dict, client: httpx.Client, settings: Settings
) -> GiosStation:
    station_id = int(raw["id"])
    readings: dict[str, float | None] = {"PM2.5": None, "PM10": None}

    for code, sensor_id in _pm_sensor_ids(station_id, client, settings).items():
        readings[code] = _latest_value(sensor_id, client, settings)

    return GiosStation(
        id=station_id,
        name=raw["stationName"],
        city=(raw.get("city") or {}).get("name") or "",
        lat=float(raw["gegrLat"]),
        lon=float(raw["gegrLon"]),
        pm25=readings["PM2.5"],
        pm10=readings["PM10"],
    )


def _pm_sensor_ids(
    station_id: int, client: httpx.Client, settings: Settings
) -> dict[str, int]:
    """Map PM param codes to sensor ids; empty on any failure."""
    try:
        response = client.get(f"{settings.gios_base_url}/station/sensors/{station_id}")
        response.raise_for_status()
        sensors = response.json()
    except (httpx.HTTPError, ValueError):
        return {}

    return {
        s["param"]["paramCode"]: int(s["id"])
        for s in sensors
        if (s.get("param") or {}).get("paramCode") in PM_CODES
    }


def _latest_value(
    sensor_id: int, client: httpx.Client, settings: Settings
) -> float | None:
    """Newest non-null value from the sensor's history; None if none."""
    try:
        response = client.get(f"{settings.gios_base_url}/data/getData/{sensor_id}")
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None

    best_date: datetime | None = None
    best_value: float | None = None
    for entry in payload.get("values", []):
        value = entry.get("value")
        if value is None:
            continue
        date = datetime.fromisoformat(entry["date"])
        if best_date is None or date > best_date:
            best_date, best_value = date, float(value)
    return best_value
