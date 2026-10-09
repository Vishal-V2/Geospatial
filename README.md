![CI](https://github.com/Vishal-V2/Geospatial/actions/workflows/ci.yml/badge.svg)

# Geospatial File Measurement API

A FastAPI service that accepts a zipped Shapefile or a KML, extracts every feature, and returns area/length
measurements computed in a suitable projected CRS (never in degrees).

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

Requires **Python 3.12+**.

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

### Try it with the sample files

The `samples/` folder holds small inputs covering normal and edge cases (see [`samples/README.md`](samples/README.md)).
Every example below uses them, run from the repository root:

```bash
curl -F "file=@samples/01_polygons_only.zip" http://127.0.0.1:8000/api/files/
```

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `GEO_DATABASE_URL` | `sqlite:///./geo.db` | Database connection string |
| `GEO_MAX_UPLOAD_MB` | `50` | Max upload size (`413` if exceeded) |
| `GEO_MAX_UNZIPPED_MB` | `300` | Max unzipped contents size |
| `GEO_MAX_FEATURES` | `100000` | Max features per upload |
<!-- VERIFY these defaults against app/config.py, and state what happens when GEO_MAX_FEATURES is exceeded -->

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

**A `201` response does not mean success.** Always check `status`. Failed uploads still return an `id` so the record
(and its error) can be retrieved later.

### Error codes

| Code | When |
|---|---|
| 201 | Upload accepted (check `status`; processing may have failed) |
| 404 | Unknown file id |
| 409 | Measurements requested for a `FAILED` or `PROCESSING` file |
| 413 | Upload too large |
| 415 | Unsupported file extension |
| 422 | Invalid query parameters (e.g. bad `limit` or `offset`) |

### Upload

```bash
curl -F "file=@samples/01_polygons_only.zip" http://127.0.0.1:8000/api/files/
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

Returns the same shape as the upload response.

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
        "coordinates": [[[10.0, 50.0], [10.0, 50.00899044894598], [10.013947827283664, 50.00899044894598], [10.013947827283664, 50.00000000000001], [10.0, 50.0]]]
      },
      "crs": "EPSG:4326",
      "properties": { "name": "Parcel A", "owner": "Alice", "zone": 1 },
      "measurement_supported": true,
      "area_sq_m": 999234.8163098362,
      "length_m": null,
      "projected_crs": "EPSG:32632",
      "note": null
    },
    {
      "index": 1,
      "layer": "parcels",
      "geometry_type": "Polygon",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[10.05, 50.0], [10.05, 50.00449522622365], [10.056973913702462, 50.00449522622365], [10.056973913702462, 50.00000000000001], [10.05, 50.0]]]
      },
      "crs": "EPSG:4326",
      "properties": { "name": "Parcel B", "owner": "Bob", "zone": 2 },
      "measurement_supported": true,
      "area_sq_m": 249823.37930830033,
      "length_m": null,
      "projected_crs": "EPSG:32632",
      "note": null
    }
  ]
}
```

Each result contains:

| Field | Meaning |
|---|---|
| `index` | Feature position within the file |
| `layer` | Source layer (shapefile name, or KML folder/document) |
| `geometry_type`, `geometry` | GeoJSON-style geometry as stored |
| `crs` | CRS of the stored geometry |
| `properties` | Feature attributes |
| `measurement_supported` | `false` for types without a defined measurement |
| `area_sq_m` / `length_m` | Polygons get an area, lines get a length, everything else gets `null` |
| `projected_crs` | CRS used for the measurement (`null` if not measured) |
| `note` | Explains repairs or why a feature was not measured |

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
    },
    {
      "index": 1,
      "layer": "parcels",
      "geometry_type": "Polygon",
      "geometry": null,
      "crs": "EPSG:4326",
      "properties": { "name": "Parcel B", "owner": "Bob", "zone": 2 },
      "measurement_supported": true,
      "area_sq_m": 249823.37930830033,
      "length_m": null,
      "projected_crs": "EPSG:32632",
      "note": null
    }
  ]
}
```

### Mixed geometry (polygon + line + point)

A zip can hold several shapefiles, one per geometry type. Polygons get an area, lines a length, and points are
returned but not measured.

```bash
curl -F "file=@samples/03_mixed_geometry.zip" http://127.0.0.1:8000/api/files/
```

The three results (polygon shortened here; its full form is shown above):

```json
[
  {
    "index": 0,
    "layer": "parcels",
    "geometry_type": "Polygon",
    "properties": { "name": "Parcel A" },
    "measurement_supported": true,
    "area_sq_m": 999234.8163098362,
    "length_m": null,
    "projected_crs": "EPSG:32632",
    "note": null
  },
  {
    "index": 1,
    "layer": "roads",
    "geometry_type": "LineString",
    "geometry": { "type": "LineString", "coordinates": [[10.0, 50.02], [10.041860846312927, 50.02]] },
    "properties": { "name": "Road 1" },
    "measurement_supported": true,
    "area_sq_m": null,
    "length_m": 2998.9967544606916,
    "projected_crs": "EPSG:32632",
    "note": null
  },
  {
    "index": 2,
    "layer": "sites",
    "geometry_type": "Point",
    "geometry": { "type": "Point", "coordinates": [10.01, 50.01] },
    "properties": { "name": "Site 1" },
    "measurement_supported": false,
    "area_sq_m": null,
    "length_m": null,
    "projected_crs": null,
    "note": "No measurement defined for points."
  }
]
```

### Unsupported geometry (handled, not a crash)

`samples/04_points_only_unsupported.zip` contains only MultiPoints. The upload completes and each feature is
returned with a note instead of a measurement:

```json
{
  "index": 0,
  "layer": "sites",
  "geometry_type": "MultiPoint",
  "geometry": { "type": "MultiPoint", "coordinates": [[10.0, 50.0], [10.001, 50.001]] },
  "crs": "EPSG:4326",
  "properties": { "name": "Cluster 1" },
  "measurement_supported": false,
  "area_sq_m": null,
  "length_m": null,
  "projected_crs": null,
  "note": "No measurement defined for points."
}
```

A KML placemark that mixes geometry types (`samples/13_kml_multigeometry_mixed.kml`) is returned as a
`GeometryCollection` with `measurement_supported: false` and the note
`"Unsupported geometry type: GeometryCollection."`.

### Invalid polygon (repaired for measurement)

`samples/05_invalid_polygon.zip` contains a self-intersecting "bowtie". It is measured on a repaired copy; the stored
geometry is unchanged and a note is added:

```json
{
  "index": 0,
  "layer": "bad",
  "geometry_type": "Polygon",
  "geometry": { "type": "Polygon", "coordinates": [[[10.1, 50.0], [10.11, 50.01], [10.11, 50.0], [10.1, 50.01], [10.1, 50.0]]] },
  "crs": "EPSG:4326",
  "properties": { "name": "Bowtie (invalid)" },
  "measurement_supported": true,
  "area_sq_m": 398434.05961789377,
  "length_m": null,
  "projected_crs": "EPSG:32632",
  "note": "Geometry was invalid; repaired for measurement."
}
```

### KML input

```bash
curl -F "file=@samples/11_sample_mixed.kml" http://127.0.0.1:8000/api/files/
```

```json
{
  "id": "41585d9b55c7",
  "filename": "11_sample_mixed.kml",
  "feature_count": 5,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "error": null
}
```

Each KML folder becomes a layer (`Parcels`, `Roads`, `Sites`). One result:

```json
{
  "index": 2,
  "layer": "Roads",
  "geometry_type": "LineString",
  "geometry": { "type": "LineString", "coordinates": [[10.0, 50.02, 0.0], [10.0418608, 50.02, 0.0]] },
  "crs": "EPSG:4326",
  "properties": { "Name": "Road 1", "description": "~3 km east-west" },
  "measurement_supported": true,
  "area_sq_m": null,
  "length_m": 2998.9934364989,
  "projected_crs": "EPSG:32632",
  "note": null
}
```
<!-- VERIFY: re-run 11_sample_mixed.kml and paste the real properties; the boilerplate filter was added after the last run -->

Notes on KML input:

- GDAL's KML driver adds boilerplate keys to every feature (`tessellate`, `extrude`, `visibility`, `drawOrder`,
  `altitudeMode`, `icon`, `timestamp`, `begin`, `end`, `id`). These are removed; real attributes are kept.
- Property names come from the driver (`Name`, `description`), so their casing differs from Shapefile attributes.
- KML coordinates may carry a Z value (`0.0`); measurement is 2D.
- KML coordinates are typically stored to 7 decimals, which is why the same polygon measures about 7 m² smaller
  from a KML than from a full-precision shapefile.

### Failed upload

```bash
curl -i -F "file=@samples/06_no_prj_should_fail.zip" http://127.0.0.1:8000/api/files/
# take the "id" from the response, then:
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

Asking for measurements of a failed file returns `409`, so an empty list is never confused with "no features":

```bash
curl -i http://127.0.0.1:8000/api/files/cab9e6cd308f/measurements/
```

```json
{ "detail": "File status is FAILED: parcels.shp has no CRS (.prj missing)." }
```

Other inputs that end as `FAILED` without crashing the service:

| Input | `error` |
|---|---|
| `samples/08_corrupt.zip` | `Invalid zip archive.` |
| `samples/09_zip_without_shapefile.zip` | `Zip does not contain a .shp file.` |
| `samples/10_zip_slip_attack.zip` | `Zip contains unsafe paths.` |
| `samples/14_kml_malformed.kml` | Generic parse error; internal paths are not exposed |

### Unsupported extension

```bash
curl -i -F "file=@samples/15_wrong_extension.txt" http://127.0.0.1:8000/api/files/
```

```json
{ "detail": "Only .zip (Shapefile) and .kml are supported." }
```

Returned with HTTP `415`; no record is created.

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
├── samples/             # Sample inputs used in the examples above
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

### File processing flow

1. Validate extension and size (`415`, `413`)
2. Stream to a temp file
3. For zips: safe unzip (`is_relative_to`, size cap); reject unsafe paths
4. Read every `.shp` (or every KML layer); reject a shapefile without `.prj`
5. Concatenate, iterate features, measure each one
6. Persist features, set status `COMPLETED` or `FAILED`

### Measurement flow

1. Unsupported type (Point, MultiPoint, GeometryCollection): return with `measurement_supported: false` and a note
2. Polygon types: check validity; if invalid, `make_valid` for measurement and add a note; if no polygonal part remains, mark unsupported
3. Choose the CRS from the centroid: UTM zone, or the polar fallback (lat ≥ 84 or ≤ -80)
4. Reproject with `shapely.transform`
5. Polygons: `.area`. Lines: `.length` (geodesic in the polar case)
6. Store the area or length, plus `projected_crs` and any note

## CRS handling

Measuring in lat/lon degrees gives meaningless numbers, so every geometry is reprojected to a projected CRS before
`.area` or `.length` is computed.

| Case | Behavior |
|---|---|
| Default | UTM zone chosen **per feature** from its centroid (e.g. `EPSG:32632` for lon 10°E). Per-feature selection handles files that span several zones |
| Polar (lat ≥ 84 or ≤ -80) | UTM is undefined. Polygon area uses equal-area `EPSG:6933`; line length uses a geodesic calculation (`pyproj.Geod`), because EPSG:6933 distorts lengths |
| Shapefile without `.prj` | **Rejected** (`FAILED`). Guessing WGS84 would silently give wrong numbers |
| KML | Assumed WGS84 (`EPSG:4326`), as required by the KML spec |
| Input already projected | The file's own CRS is reported in `crs` (e.g. `EPSG:32632`); measurement still uses the feature's UTM zone, so data already in that zone gives identical results to the same data in lat/lon |
| Several shapefiles with different CRSs in one zip | All are reprojected to the first shapefile's CRS; stored geometry and `crs` then reflect that first CRS |
| Invalid polygon | Repaired with `shapely.make_valid` **for measurement only**. Stored geometry is unchanged and a `note` is added. If nothing polygonal remains after repair the feature is marked unsupported |
<!-- VERIFY the "Input already projected" row with a shapefile in EPSG:3857 (check projected_crs and area) -->

### Accuracy note

UTM is not perfectly distance- or area-preserving away from its central meridian. For the 1 km square at lon 10°E in
zone 32 (central meridian 9°E), the UTM area is 999,234.8 m² against a geodesic reference of about 999,907 m² (-0.07%).
That matches the expected UTM scale factor (~0.99966, squared for area), so it is a property of the projection and not
an error in the code. A test in the suite asserts line lengths within 0.5% of a geodesic reference.

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
| Failed upload returns `201` with `status: FAILED`, `id` and `error` | The failed record stays retrievable via GET. Validation errors (`415`, `413`) stay real 4xx errors |
| Measurements of a `FAILED`/`PROCESSING` file return `409` | An empty `200` would look the same as a file with no features; the error is in the body |
| KML boilerplate keys filtered | GDAL adds `tessellate`, `extrude`, `visibility`, etc.; only those are removed, user attributes are kept |
| Parse errors return a generic message | Temp paths like `/tmp/.../upload.kml` are not leaked to clients |

## Limitations

- Only Polygon, MultiPolygon, LineString and MultiLineString are measured. Points, MultiPoints and GeometryCollections
  are returned with `measurement_supported: false` and a note.
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

- **Degrees vs projected CRS:** Features in `EPSG:4326` have coordinates in degrees, so calling `.area` on them
  returns square degrees, which means nothing. Reprojecting to a UTM zone first is what makes the numbers real metres.
- **Failed upload as 201 + FAILED:** In production I'd probably return `202 Accepted` with a polling endpoint, but for
  this scope the synchronous `status` field works and keeps the failed record queryable. The matching downside is that
  `201` can hide a failure, so the README says to always check `status`.
- **Invalid polygon repair:** `make_valid` can change the geometry type (a bowtie becomes two lobes, a degenerate
  polygon can collapse to a line), so I re-check the type after repair and mark the feature unsupported if nothing
  polygonal remains.
- **Zip-slip bypass:** `startswith("/tmp/abc")` also passes for `/tmp/abc_evil`; `Path.is_relative_to` is the correct check.
- **Test DB isolation:** The `commit()` inside `process_file` broke rollback-based fixtures. Dropping and recreating the
  tables around each test fixed it cleanly, and keeps tests off the real `geo.db`.
- **UTM accuracy:** Comparing a manual result against a geodesic reference showed a -0.07% difference. It matched the
  UTM scale factor at 10°E to within a few m², so it is projection distortion, not a bug.
- **Manual edge-case pass:** Running a pack of 15 sample files (corrupt zip, zip-slip, missing `.prj`,
  GeometryCollection, malformed KML) showed that bad input ends as a readable `FAILED` or an "unsupported" note, never
  a server error.

## CI/CD

- **GitHub Actions** (`.github/workflows/ci.yml`):
  - `test` — pytest on Ubuntu, Python 3.12
  - `lint` — ruff check
  - `docker-smoke` — builds the image, runs the container, uploads `sample.kml`, verifies measurements
- **Concurrency control** — cancels in-progress runs on new pushes
- **Docker multi-stage build** — smaller image, non-root user, health check (urllib)
- **Requirements** — production deps in `requirements.txt`; dev deps (`pytest`, `httpx`, `ruff`) in `requirements-dev.txt`