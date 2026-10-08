![CI](https://github.com/Vishal-V2/Geospatial/actions/workflows/ci.yml/badge.svg)

# Geospatial File Measurement API

A FastAPI service that accepts a zipped Shapefile or a KML, extracts features, and returns area/length measurements computed in a suitable projected CRS.

## Stack
- **FastAPI** ≥0.110 — API framework, auto OpenAPI docs
- **uvicorn[standard]** ≥0.29 — ASGI server
- **python-multipart** ≥0.0.9 — multipart/form-data parsing
- **GeoPandas** ≥0.14 + **pyogrio** ≥0.7 — Shapefile/KML reading (bundled GDAL)
- **Shapely** ≥2.0 — geometry operations
- **pyproj** ≥3.6 — CRS transformations
- **SQLAlchemy** ≥2.0 + **SQLite** — ORM & storage (swappable to PostgreSQL via `GEO_DATABASE_URL`, driver not included)
- **pydantic-settings** ≥2.2 — environment-based config
- **pytest** ≥8 + **httpx** ≥0.27 — testing
- **ruff** — linting (CI)

Requires **Python 3.12+**

## Setup

### Local

```bash
git clone https://github.com/Vishal-V2/Geospatial.git
cd Geospatial
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs: http://127.0.0.1:8000/docs

### Docker

```bash
docker compose up --build
```

### Tests and lint

```bash
pip install -r requirements-dev.txt
pytest
ruff check app tests
```

## API

| Method | Path | Description |
|---|---|---|
| POST | `/api/files/` | Upload a `.zip` (Shapefile) or `.kml` |
| GET | `/api/files/{id}/` | File metadata and processing status |
| GET | `/api/files/{id}/measurements/` | Per-feature measurements (paginated) |

### Status values

| Status | Meaning |
|---|---|
| `PROCESSING` | Transient, while the file is being read |
| `COMPLETED` | All features extracted and measured where supported |
| `FAILED` | Processing failed; see `error` |

**A `201` response does not mean success.** Always check `status`. Failed uploads still return an `id` so the record (and its error) can be retrieved later. Real 4xx errors are returned only for `415` (unsupported extension) and `413` (file too large).

### Upload

```bash
curl -F "file=@01_polygons_only.zip" http://127.0.0.1:8000/api/files/
```

```json
{
  "id": "a48d75a474dd",
  "filename": "01_polygons_only.zip",
  "feature_count": 2,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "error": null
}
```

### File details

```bash
curl http://127.0.0.1:8000/api/files/a48d75a474dd/
```

```json
{
  "id": "a48d75a474dd",
  "filename": "01_polygons_only.zip",
  "feature_count": 2,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "error": null
}
```

### Measurements

```bash
curl http://127.0.0.1:8000/api/files/a48d75a474dd/measurements/
```

```json
{
  "file_id": "a48d75a474dd",
  "total": 2,
  "limit": 100,
  "offset": 0,
  "results": [
    {
      "index": 0,
      "layer": "parcels",
      "geometry_type": "Polygon",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[10.0, 50.0], [10.0, 50.00899], [10.01395, 50.00899], [10.01395, 50.0], [10.0, 50.0]]]
      },
      "crs": "EPSG:4326",
      "properties": { "name": "Parcel A", "owner": "Alice", "zone": 1 },
      "measurement_supported": true,
      "area_sq_m": 999234.8163098362,
      "length_m": null,
      "projected_crs": "EPSG:32632",
      "note": null
    }
  ]
}
```

(Second feature and full-precision coordinates omitted here for brevity.)

**Query parameters**

| Param | Default | Description |
|---|---|---|
| `limit` | `100` | Page size |
| `offset` | `0` | Number of features to skip |
| `include_geometry` | `true` | Set to `false` to omit geometry; the `geometry` field is then `null` |

```bash
curl "http://127.0.0.1:8000/api/files/a48d75a474dd/measurements/?include_geometry=false"
```

```json
{
  "file_id": "a48d75a474dd",
  "total": 2,
  "limit": 100,
  "offset": 0,
  "results": [
    {
      "index": 0,
      "layer": "parcels",
      "geometry_type": "Polygon",
      "geometry": null,
      "crs": "EPSG:4326",
      "properties": { "name": "Parcel A", "owner": "Alice", "zone": 1 },
      "measurement_supported": true,
      "area_sq_m": 999234.8163098362,
      "length_m": null,
      "projected_crs": "EPSG:32632",
      "note": null
    }
  ]
}
```

### Mixed geometry (polygon + line + point)

Points are returned but not measured.

```json
{
  "index": 2,
  "layer": "sites",
  "geometry_type": "Point",
  "geometry": { "type": "Point", "coordinates": [10.01, 50.01] },
  "crs": "EPSG:4326",
  "properties": { "name": "Site 1" },
  "measurement_supported": false,
  "area_sq_m": null,
  "length_m": null,
  "projected_crs": null,
  "note": "No measurement defined for points."
}
```

### Failed upload (different ID from the success example)

```bash
curl -i -F "file=@06_no_prj_should_fail.zip" http://127.0.0.1:8000/api/files/
curl http://127.0.0.1:8000/api/files/cab9e6cd308f/
```

```json
{
  "id": "cab9e6cd308f",
  "filename": "06_no_prj_should_fail.zip",
  "feature_count": 0,
  "crs": null,
  "status": "FAILED",
  "error": "parcels.shp has no CRS (.prj missing)."
}
```

```bash
curl "http://127.0.0.1:8000/api/files/cab9e6cd308f/measurements/"
```

```json
{ "detail": "File status is FAILED: parcels.shp has no CRS (.prj missing)." }
```

(Returned with HTTP `409`.)

### Unsupported extension

```bash
curl -i -F "file=@15_wrong_extension.txt" http://127.0.0.1:8000/api/files/
```

```json
{ "detail": "Only .zip (Shapefile) and .kml are supported." }
```

(Returned with HTTP `415`.)

## Architecture

```
Geospatial/
├── app/
│   ├── __init__.py
│   ├── main.py          # app setup and /health
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
├── requirements-dev.txt
├── pyproject.toml       # pytest + ruff config
├── Dockerfile           # Multi-stage, non-root, health check (urllib)
├── docker-compose.yml   # SQLite volume
├── .dockerignore
├── .github/workflows/ci.yml
├── .gitignore
└── README.md
```

### File Processing Flow
Upload → validate → stream to temp → safe unzip (`is_relative_to`) → read all layers → iterate features → persist → set status

### Measurement Flow
Geometry type check → pick UTM from centroid → reproject (`shapely.transform`) → `.area` / `.length` → store

## CRS handling

Measuring in lat/lon degrees gives meaningless numbers, so every geometry is reprojected to a projected CRS before `.area` or `.length` is computed.

| Case | Behavior |
|---|---|
| Default | UTM zone chosen **per feature** from its centroid (e.g. `EPSG:32632` for lon 10°E). Per-feature selection handles files that span several zones |
| Polar (lat ≥ 84 or ≤ -80) | UTM is undefined. Polygon area uses equal-area `EPSG:6933`; line length uses a geodesic calculation (`pyproj.Geod`), because EPSG:6933 distorts lengths |
| Shapefile without `.prj` | **Rejected** (`FAILED`). Guessing WGS84 would silently give wrong numbers |
| KML | Assumed WGS84 (`EPSG:4326`), as required by the KML spec |
| Input already projected | Kept as the stored CRS (e.g. `EPSG:32632`) and measured in that projection's units |
| Invalid polygon | Repaired with `shapely.make_valid` **for measurement only**. Stored geometry is unchanged and a `note` is added. If nothing polygonal remains after repair the feature is marked unsupported |
| Stored geometry and CRS | Original geometry and CRS are preserved per feature. **Exception:** if a zip contains several shapefiles with different CRSs, all are reprojected to the first shapefile's CRS before measurement |

### Accuracy note

UTM is not perfectly distance- or area-preserving away from its central meridian. For the 1 km square at lon 10°E in zone 32 (central meridian 9°E), the UTM area is 999,234.8 m² against a geodesic reference of 999,907 m² (-0.07%). This matches the expected UTM scale factor (~0.99966 squared), so it is a property of the projection and not an error in the code. A geodesic test in the suite asserts line lengths within 0.5%.

## Design decisions

| Decision | Why |
|---|---|
| Per-feature UTM zone | EPSG:3857 distorts area; per-feature handles mixed-region files |
| Polar fallback (6933 for area, geodesic for length) | 6933 is equal-area but distorts lengths |
| Reject Shapefile with no `.prj` | Silent guessing gives wrong numbers |
| Read all KML layers | KML folders become separate GDAL layers |
| Read each `.shp` in a zip separately and concatenate | A Shapefile cannot mix geometry types, so mixed data means several `.shp` files |
| `make_valid` for measurement only | Keeps the user's geometry intact; the repaired shape is used only for the number |
| Zip-slip guard with `Path.is_relative_to` plus size cap | `startswith` can be bypassed by sibling paths like `/tmp/abc_evil` |
| Synchronous processing plus a `status` field | Simple now, async-ready later |
| SQLite with JSON columns | Zero setup; a Postgres URL is a possible later step (driver not included) |
| Failed upload returns `201` with `status: FAILED`, `id` and `error` | The failed record stays retrievable via GET. 415 and 413 stay real 4xx errors |
| Failed/procesing file measurements return `409` | Prevents confusion with empty results; error is in response body |
| KML boilerplate keys filtered | GDAL adds `tessellate`, `extrude`, `visibility`, etc.; only `Name`/`description` kept |
| Parse errors return generic message | Temp paths like `/tmp/.../upload.kml` are not leaked to clients |

## Limitations

- Only Polygon, MultiPolygon, LineString and MultiLineString are measured. Points, MultiPoints and GeometryCollections are returned with `measurement_supported: false` and a note.
- A single feature that spans several UTM zones is measured in one zone (chosen from its centroid).
- Processing is synchronous, so very large files block the request.
- No delete endpoint. No KMZ or GeoJSON input.
- A declared `.zip` size is checked, but a spoofed header is only caught by the extraction size cap.

## Future scope

- Async processing with a task queue (the `status` field is already in place)
- Postgres/PostGIS storage (add a driver; JSON columns would move to geometry types)
- KMZ and GeoJSON input
- Measuring the members of a GeometryCollection individually
- Delete endpoint and file retention policy
- Geodesic measurement for features that span multiple zones

## Learnings

- **Measuring in degrees vs projected CRS:** The first time I saw 0.0001°² reported as an "area," it was clearly wrong. Projected CRS is non-negotiable for metric measurements.
- **Failed upload as 201 + FAILED:** In production I'd probably return 202 Accepted with a polling endpoint, but for this scope the synchronous status field works and keeps the failed record queryable.
- **Invalid polygon repair:** `make_valid` can turn a bowtie into a MultiPolygon of two lobes, but a degenerate line becomes a LineString — you must re-check the geometry type after repair.
- **Zip-slip bypass:** `startswith("/tmp/abc")` passes for `/tmp/abc_evil`; `is_relative_to` is the correct check.
- **Test DB isolation:** The `commit()` in `process_file` broke rollback-based fixtures. Switching to `drop_all/create_all` per test fixed it cleanly.
- **UTM accuracy check:** The -0.07% error on a 1 km square at 10°E matched the UTM scale factor (0.99966²) exactly — the test caught a real projection artifact, not a bug.

## CI/CD

- **GitHub Actions** (`.github/workflows/ci.yml`):
  - `test` — pytest on Ubuntu 3.12
  - `lint` — ruff check
  - `docker-smoke` — builds image, runs container, uploads sample.kml, verifies measurements
- **Concurrency control** — cancels in-progress runs on new pushes
- **Docker multi-stage build** — smaller image, non-root user, health check (urllib)
- **Requirements** — production deps in `requirements.txt`; dev deps (`pytest`, `httpx`, `ruff`) in `requirements-dev.txt`