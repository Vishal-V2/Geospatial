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


def test_shapefile_upload(valid_shapefile_zip: bytes):
    r = client.post("/api/files/", files={"file": ("test.zip", valid_shapefile_zip)})
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 2

    fid = data["id"]
    res = client.get(f"/api/files/{fid}/measurements/").json()["results"]
    types = {x["geometry_type"] for x in res}
    assert types == {"Polygon"}

    for poly in res:
        assert poly["measurement_supported"] is True
        assert poly["area_sq_m"] is not None
        assert 1.0e6 < poly["area_sq_m"] < 1.3e6


def test_shapefile_missing_prj(invalid_shapefile_zip: bytes):
    r = client.post("/api/files/", files={"file": ("test.zip", invalid_shapefile_zip)})
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "FAILED"
    assert data["id"] is not None
    assert data["error"] is not None
    assert ".prj" in data["error"] or "CRS" in data["error"] or "crs" in data["error"].lower()

    # Verify we can retrieve the failed record
    fid = data["id"]
    r2 = client.get(f"/api/files/{fid}/")
    assert r2.status_code == 200
    assert r2.json()["status"] == "FAILED"


def test_corrupt_zip(corrupt_zip: bytes):
    r = client.post("/api/files/", files={"file": ("bad.zip", corrupt_zip)})
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "FAILED"
    assert data["id"] is not None
    assert data["error"] is not None
    assert "invalid" in data["error"].lower() or "zip" in data["error"].lower()


def test_zip_slip(zip_slip_zip: bytes):
    r = client.post("/api/files/", files={"file": ("evil.zip", zip_slip_zip)})
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "FAILED"
    assert data["id"] is not None
    assert data["error"] is not None
    assert "unsafe" in data["error"].lower() or "path" in data["error"].lower()


def test_no_shp_in_zip(no_shp_zip: bytes):
    r = client.post("/api/files/", files={"file": ("empty.zip", no_shp_zip)})
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "FAILED"
    assert data["id"] is not None
    assert data["error"] is not None
    assert ".shp" in data["error"].lower() or "shapefile" in data["error"].lower()


def test_mixed_geometry_zip(mixed_geometry_zip: bytes):
    r = client.post("/api/files/", files={"file": ("mixed.zip", mixed_geometry_zip)})
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "COMPLETED"
    assert data["feature_count"] == 3

    fid = data["id"]
    res = client.get(f"/api/files/{fid}/measurements/").json()["results"]
    types = {x["geometry_type"] for x in res}
    assert types == {"Polygon", "LineString", "Point"}

    # Polygon has area
    poly = next(x for x in res if x["geometry_type"] == "Polygon")
    assert poly["measurement_supported"] is True
    assert poly["area_sq_m"] is not None
    assert poly["area_sq_m"] > 0

    # LineString has length
    line = next(x for x in res if x["geometry_type"] == "LineString")
    assert line["measurement_supported"] is True
    assert line["length_m"] is not None
    assert line["length_m"] > 0

    # Point is unsupported
    point = next(x for x in res if x["geometry_type"] == "Point")
    assert point["measurement_supported"] is False
