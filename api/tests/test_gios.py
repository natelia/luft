import json
import re
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.gios import GiosError, fetch_all

FIXTURES = Path(__file__).parent / "fixtures"
TEST_SETTINGS = Settings(gios_base_url="https://gios.test/rest")


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def _gios_handler(request: httpx.Request) -> httpx.Response:
    """Serve recorded GIOS responses; no real network involved."""
    path = request.url.path
    if path.endswith("station/findAll"):
        return httpx.Response(200, json=_load("findAll.json"))
    if match := re.search(r"sensors/(\d+)$", path):
        return httpx.Response(200, json=_load(f"sensors_{match[1]}.json"))
    if match := re.search(r"getData/(\d+)$", path):
        return httpx.Response(200, json=_load(f"data_{match[1]}.json"))
    return httpx.Response(404, json={"error": "fixture not found"})


@pytest.fixture
def gios_client() -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(_gios_handler))


def test_snapshot_parses_stations_and_values(gios_client):
    snapshot = fetch_all(TEST_SETTINGS, client=gios_client)

    assert len(snapshot) == 2
    by_id = {s.id: s for s in snapshot}

    krakow = by_id[400]
    assert krakow.name == "Kraków, al. Krasińskiego"
    assert krakow.city == "Kraków"
    assert krakow.lat == pytest.approx(50.057678)
    assert krakow.lon == pytest.approx(19.926452)
    assert krakow.pm25 == 31.1  # newest entry is null -> previous hour wins
    assert krakow.pm10 == 49.0


def test_missing_pm25_becomes_none(gios_client):
    snapshot = fetch_all(TEST_SETTINGS, client=gios_client)

    nowy_sacz = next(s for s in snapshot if s.id == 114)
    assert nowy_sacz.pm25 is None  # sensor exists but its history is all-null
    assert nowy_sacz.pm10 == 41.0


def test_findall_500_raises_gios_error():
    broken = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    )

    with pytest.raises(GiosError):
        fetch_all(TEST_SETTINGS, client=broken)
