# Geospatial File Measurement API

A FastAPI service that accepts a zipped Shapefile or a KML, extracts features, and returns area/length measurements computed in a suitable projected CRS.

## Stack
- **FastAPI** ≥0.110 — API framework, auto OpenAPI docs
- **uvicorn[standard]** ≥0.29 — ASGI server
- **python-multipart** ≥0.0.9 — multipart/form-data parsing
- **GeoPandas** ≥0.14 + **pyogrio** ≥0.7 — Shapefile/KML reading (bundled GDAL)
- **Shapely** ≥2.0 — geometry operations
- **pyproj** ≥3.6 — CRS transformations
- **SQLAlchemy** ≥2.0 + **SQLite** — ORM & storage (PostGIS-ready)
- **pydantic-settings** ≥2.2 — environment-based config
- **pytest** ≥8 + **httpx** ≥0.27 — testing

Requires **Python 3.12+**

## Setup

```bash
git clone <repo-url>
cd geo-measure-api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# Swagger UI → http://127.0.0.1:8000/docs
```

### Environment Variables
- `GEO_DATABASE_URL` — default `sqlite:///./geo.db`
- `GEO_MAX_UPLOAD_MB` — default `50`
- `GEO_MAX_UNZIPPED_MB` — default `300`
- `GEO_MAX_FEATURES` — default `100000`

### Docker
```bash
docker build -t geo-measure-api .
docker run -p 8000:8000 geo-measure-api
```

### Tests
```bash
pytest -v
```

## API

### POST `/api/files/`
Upload a `.zip` (Shapefile) or `.kml` file.

**Response (201):**
```json
{
  "id": "a1b2c3d4e5f6",
  "filename": "survey.kml",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "error": null
}
```

### GET `/api/files/{id}/`
Returns file metadata.

### GET `/api/files/{id}/measurements/?limit=100&offset=0`
Returns paginated feature measurements.

**KML Response Example:**
```json
{
  "file_id": "a1b2c3d4e5f6",
  "total": 3,
  "limit": 100,
  "offset": 0,
  "results": [
    {
      "index": 0,
      "layer": "Document",
      "geometry_type": "Polygon",
      "geometry": {"type": "Polygon", "coordinates": [[[77.2, 28.6], "..."]]},
      "crs": "EPSG:4326",
      "properties": {"Name": "Plot A"},
      "measurement_supported": true,
      "area_sq_m": 1089532.4,
      "length_m": null,
      "projected_crs": "EPSG:32643",
      "note": null
    },
    {
      "index": 2,
      "geometry_type": "Point",
      "measurement_supported": false,
      "note": "No measurement defined for points."
    }
  ]
}
```

**Shapefile Response Example** (layer = shapefile stem):
```json
{
  "file_id": "b2c3d4e5f6a1",
  "total": 2,
  "limit": 100,
  "offset": 0,
  "results": [
    {
      "index": 0,
      "layer": "test",
      "geometry_type": "Polygon",
      "geometry": {"type": "Polygon", "coordinates": [[[77.2, 28.6], "..."]]},
      "crs": "EPSG:4326",
      "properties": {"name": "Plot A"},
      "measurement_supported": true,
      "area_sq_m": 1089532.4,
      "length_m": null,
      "projected_crs": "EPSG:32643",
      "note": null
    }
  ]
}
```

### Errors
- `413` — File too large
- `415` — Unsupported file type (only `.zip` and `.kml`)
- `404` — File not found
- `201` with `status: "FAILED"` — Processing error (corrupt file, missing `.shp`/`.prj`, etc.); response body includes `id` and `error` message

## Architecture

```
geo-measure-api/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app, routes
│   ├── config.py        # Pydantic settings
│   ├── db.py            # SQLAlchemy engine/session
│   ├── models.py        # ORM models (UploadedFile, Feature)
│   ├── schemas.py       # Pydantic response models
│   ├── api/
│   │   ├── __init__.py
│   │   └── files.py     # Upload, file info, measurements endpoints
│   └── services/
│       ├── __init__.py
│       ├── readers.py   # Shapefile/KML → GeoDataFrame (safe unzip)
│       ├── crs.py       # UTM zone selection, reprojection
│       ├── measure.py   # Area/length logic per geometry type
│       └── ingest.py    # Orchestration: read → measure → persist
├── tests/
│   ├── __init__.py
│   ├── conftest.py      # Shapefile fixtures
│   ├── test_measure.py  # Unit tests for measurement logic
│   ├── test_api.py      # API integration tests
│   └── data/
│       └── sample.kml   # Sample KML for testing
├── requirements.txt
├── Dockerfile
├── .gitignore
└── README.md
```

### File Processing Flow
Upload → validate → stream to temp → safe unzip → read all layers → iterate features → persist → set status

### Measurement Flow
Geometry type check → pick UTM from centroid → reproject → `.area` / `.length` → store

### CRS Handling
- KML: assumed WGS84 (EPSG:4326)
- Shapefile: CRS from `.prj`; missing `.prj` rejected
- Multi-shapefile zips: all shapefiles reprojected to the first shapefile's CRS before measurement
- Measurements never in degrees; original geometry + CRS preserved in database
- Invalid polygons repaired for measurement using `shapely.make_valid` (original stored unchanged)

## Design Decisions

| Decision | Alternatives Considered | Why |
|----------|------------------------|-----|
| FastAPI | Django + DRF | Lighter, typed schemas, built-in docs |
| pyogrio/GeoPandas | fiona, `fastkml`, `pyshp` | One API for both formats, faster, bundled GDAL |
| Per-feature UTM | One CRS per file, EPSG:3857, geodesic | 3857 distorts area. Per-feature keeps accuracy for mixed-region files |
| Sync processing + status | Celery/RQ | Simpler for the scope, and the status field makes the move to async easy |
| SQLite + JSON columns | PostGIS | Zero setup. Swap the URL for Postgres later |
| Reject Shapefiles with no `.prj` | Assume 4326 | Silent guessing gives wrong measurements |
| Store GeoJSON in the source CRS | Store reprojected | Preserves the user's data |

## Limitations
- Geometries spanning multiple UTM zones lose accuracy
- Polar regions (lat ≥ 84° or ≤ -80°): polygon areas use EPSG:6933 (equal-area); line lengths use geodesic (WGS84) for accuracy
- Z values ignored
- No auth/rate limiting
- Zip size limit based on declared header sizes (can be spoofed)

## Future Scope
- Async processing with Celery/Redis plus a polling endpoint
- Geodesic measurements using `pyproj.Geod` for comparison or large features
- PostGIS storage with spatial queries
- Perimeter for polygons, and unit conversion (`?units=ha|acre|km`)
- More formats (GeoJSON, GPKG, KMZ)
- Authentication, rate limiting, and object storage (S3) for uploads
- Pagination via cursors, CSV/GeoJSON export, and a CI pipeline (GitHub Actions)