from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
KML = Path(__file__).parent / "data" / "sample.kml"


def test_upload_and_measure():
    r = client.post("/api/files/", files={"file": ("sample.kml", KML.read_bytes())})
    assert r.status_code == 201
    fid = r.json()["id"]
    assert r.json()["status"] == "COMPLETED"

    assert client.get(f"/api/files/{fid}/").json()["feature_count"] == 3
    res = client.get(f"/api/files/{fid}/measurements/").json()["results"]
    assert {x["geometry_type"] for x in res} == {"Polygon", "LineString", "Point"}


def test_rejects_bad_extension():
    assert client.post("/api/files/", files={"file": ("a.txt", b"x")}).status_code == 415


def test_404():
    assert client.get("/api/files/nope/").status_code == 404