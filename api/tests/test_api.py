from datetime import datetime, timedelta, timezone

from app.models import Measurement, Station


def _hour_ago(hours: float) -> datetime:
    """UTC hour boundary `hours` back — the hour an ingest would store."""
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return now - timedelta(hours=hours)


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_station_measurements_24h(client, seed):
    seed(
        Station(id=400, name="al. Krasińskiego", city="Kraków", lat=50.06, lon=19.93),
    )
    seed(
        Measurement(station_id=400, measured_hour=_hour_ago(1), pm25=12.5, pm10=20.0),
        Measurement(station_id=400, measured_hour=_hour_ago(25), pm25=99.9, pm10=150.0),
    )

    r = client.get("/stations/400/measurements")  # default range: 24h

    assert r.status_code == 200
    body = r.json()
    assert body["station_id"] == 400
    assert body["points"] == [
        {
            "measured_hour": _hour_ago(1).strftime("%Y-%m-%dT%H:00:00+00:00"),
            "pm25": 12.5,
            "pm10": 20.0,
        }
    ]  # the 25h-old point is out of range


def test_station_measurements_7d_includes_older_points(client, seed):
    seed(
        Station(id=400, name="al. Krasińskiego", city="Kraków", lat=50.06, lon=19.93),
    )
    seed(
        Measurement(station_id=400, measured_hour=_hour_ago(1), pm25=12.5, pm10=20.0),
        Measurement(station_id=400, measured_hour=_hour_ago(25), pm25=99.9, pm10=150.0),
    )

    r = client.get("/stations/400/measurements", params={"range": "7d"})

    assert r.status_code == 200
    points = r.json()["points"]
    assert len(points) == 2
    assert points[0]["pm25"] == 99.9  # oldest first
    assert points[1]["pm25"] == 12.5


def test_station_measurements_unknown_station_404(client):
    r = client.get("/stations/999/measurements")

    assert r.status_code == 404
    assert r.json() == {"error": "nieznana stacja"}


def test_station_measurements_bad_range_422(client, seed):
    seed(
        Station(id=400, name="al. Krasińskiego", city="Kraków", lat=50.06, lon=19.93),
    )

    r = client.get("/stations/400/measurements", params={"range": "30d"})

    assert r.status_code == 422
    assert r.json() == {"error": "nieobsługiwany zakres"}


def test_stations_list(client, seed):
    seed(
        Station(id=400, name="al. Krasińskiego", city="Kraków", lat=50.06, lon=19.93),
        Station(id=114, name="ul. Nawojowska", city="Nowy Sącz", lat=49.62, lon=20.72),
    )

    r = client.get("/stations")

    assert r.status_code == 200
    body = r.json()
    assert [s["id"] for s in body] == [400, 114]  # ordered by city, then name
    krakow = body[0]
    assert krakow["name"] == "al. Krasińskiego"
    assert krakow["city"] == "Kraków"
    assert krakow["lat"] == 50.06
    assert krakow["lon"] == 19.93


def test_stations_search_q(client, seed):
    seed(
        Station(id=400, name="al. Krasińskiego", city="Kraków", lat=50.06, lon=19.93),
        Station(id=114, name="ul. Nawojowska", city="Nowy Sącz", lat=49.62, lon=20.72),
    )

    r = client.get("/stations", params={"q": "krak"})

    assert r.status_code == 200
    assert [s["id"] for s in r.json()] == [400]
