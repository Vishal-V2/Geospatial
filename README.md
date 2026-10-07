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
- **ruff** — linting (CI)

Requires **Python 3.12+**

## Setup

```bash
git clone <repo-url>
cd Geospatial
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

**Multi-stage build** — builder stage installs deps, runtime stage copies only needed artifacts, runs as non-root user with health check.

### Tests
```bash
pytest -v
```

### Lint
```bash
ruff check app tests
```

## API

### POST `/api/files/`
Upload a `.zip` (Shapefile) or `.kml` file.

**Response (201) — Success:**
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

**Response (201) — Processing Failed:**
```json
{
  "id": "a1b2c3d4e5f6",
  "filename": "bad.zip",
  "feature_count": 0,
  "crs": null,
  "status": "FAILED",
  "error": "Zip does not contain a .shp file."
}
```

### GET `/api/files/{id}/`
Returns file metadata.

### GET `/api/files/{id}/measurements/?limit=100&offset=0&include_geometry=true`
Returns paginated feature measurements.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 100 | Page size (1–1000) |
| `offset` | int | 0 | Pagination offset |
| `include_geometry` | bool | true | Exclude geometry to reduce payload |

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
│   ├── config.py        # Pydantic settings (SettingsConfigDict)
│   ├── db.py            # SQLAlchemy engine/session
│   ├── models.py        # ORM models (UploadedFile, Feature)
│   ├── schemas.py       # Pydantic response models
│   ├── api/
│   │   ├── __init__.py
│   │   └── files.py     # Upload, file info, measurements endpoints
│   └── services/
│       ├── __init__.py
│       ├── readers.py   # Shapefile/KML → GeoDataFrame (safe unzip)
│       ├── crs.py       # UTM zone selection, reprojection (shapely.transform)
│       ├── measure.py   # Area/length logic per geometry type
│       └── ingest.py    # Orchestration: read → measure → persist
├── tests/
│   ├── __init__.py
│   ├── conftest.py      # DB fixtures, shapefile fixtures
│   ├── test_measure.py  # Unit tests for measurement logic
│   ├── test_api.py      # API integration tests
│   └── data/
│       └── sample.kml   # Sample KML for testing
├── scripts/
│   └── smoke_test.sh    # Docker CI smoke test
├── requirements.txt
├── pyproject.toml       # pytest + ruff config
├── Dockerfile           # Multi-stage, non-root, health check
├── docker-compose.yml   # SQLite volume, optional PostGIS
├── .gitignore
└── README.md
```

### File Processing Flow
Upload → validate → stream to temp → safe unzip (`is_relative_to`) → read all layers → iterate features → persist → set status

### Measurement Flow
Geometry type check → pick UTM from centroid → reproject (`shapely.transform`) → `.area` / `.length` → store

### CRS Handling
- KML: assumed WGS84 (EPSG:4326)
- Shapefile: CRS from `.prj`; missing `.prj` rejected
- Multi-shapefile zips: all shapefiles reprojected to the first shapefile's CRS before measurement
- Measurements never in degrees; original geometry + CRS preserved in database
- Invalid polygons repaired for measurement using `shapely.make_valid` (original stored unchanged)
- Polar regions (lat ≥ 84° or ≤ -80°): polygon areas use EPSG:6933 (equal-area); line lengths use geodesic (WGS84)

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

## Learnings
- KML folders arrive as multiple GDAL layers
- A missing `.prj` means an unknown CRS, so rejecting it is safer than guessing
- UTM isn't equal-area, but the error is tiny inside a zone (verified against Geod within 0.5%)
- `make_valid` can change a geometry's type, so you must re-check the result
- A service-level `commit()` broke rollback-based test isolation
- A Shapefile can't mix geometry types in one layer
- Zip-slip and zip-bomb defenses

## CI/CD
- **GitHub Actions** (`.github/workflows/ci.yml`):
  - `test` — pytest on Ubuntu 3.12
  - `lint` — ruff check
  - `docker-smoke` — builds image, runs container, uploads sample.kml, verifies measurements
- **Concurrency control** — cancels in-progress runs on new pushes
- **Docker multi-stage build** — smaller image, non-root user, health check

## Future Scope
- Async processing with Celery/Redis plus a polling endpoint
- Geodesic measurements using `pyproj.Geod` for comparison or large features
- PostGIS storage with spatial queries
- Perimeter for polygons, and unit conversion (`?units=ha|acre|km`)
- More formats (GeoJSON, GPKG, KMZ)
- Authentication, rate limiting, and object storage (S3) for uploads
- Pagination via cursors, CSV/GeoJSON export