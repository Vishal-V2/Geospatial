# Geospatial File Measurement API

A FastAPI service that accepts a zipped Shapefile or a KML, extracts features, and returns area/length measurements computed in a suitable projected CRS.

## Stack
- FastAPI · GeoPandas + pyogrio (GDAL) · Shapely 2 · pyproj · SQLAlchemy 2 + SQLite · pytest

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
pytest -q
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

**Response:**
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

### Errors
- `413` — File too large
- `415` — Unsupported file type (only `.zip` and `.kml`)
- `404` — File not found
- `422` — Corrupt file, missing `.shp`/`.prj`, or processing error

## Architecture

```
app/
├── main.py          # FastAPI app, routes
├── config.py        # Pydantic settings
├── db.py            # SQLAlchemy engine/session
├── models.py        # ORM models (UploadedFile, Feature)
├── schemas.py       # Pydantic response models
├── api/
│   └── files.py     # Upload, file info, measurements endpoints
└── services/
    ├── readers.py   # Shapefile/KML → GeoDataFrame (safe unzip)
    ├── crs.py       # UTM zone selection, reprojection
    ├── measure.py   # Area/length logic per geometry type
    └── ingest.py    # Orchestration: read → measure → persist
```

### File Processing Flow
Upload → validate → stream to temp → safe unzip → read all layers → iterate features → persist → set status

### Measurement Flow
Geometry type check → pick UTM from centroid → reproject → `.area` / `.length` → store

### CRS Handling
- KML: assumed WGS84 (EPSG:4326)
- Shapefile: CRS from `.prj`; missing `.prj` rejected
- Measurements never in degrees; original geometry + CRS preserved

## Design Decisions

| Decision | Why |
|----------|-----|
| FastAPI | Light, typed, auto docs |
| pyogrio/GeoPandas | One API for both formats, bundled GDAL |
| Per-feature UTM | 3857 distorts area; per-feature keeps accuracy |
| Sync + status | Simple, async-ready |
| SQLite + JSON | Zero setup, swap to PostGIS later |
| Reject no `.prj` | Silent guessing = wrong measurements |
| Store GeoJSON in source CRS | Preserves user data |

## Limitations
- Geometries spanning multiple UTM zones lose accuracy
- Polar regions use EPSG:6933 fallback
- Z values ignored
- No auth/rate limiting

## Future Scope
- Async processing with Celery/Redis
- Geodesic measurements via `pyproj.Geod`
- PostGIS with spatial queries
- More formats (GeoJSON, GPKG, KMZ)
- Auth, rate limiting, S3 uploads
- CI/CD pipeline