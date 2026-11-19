from app.models import Station


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


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
