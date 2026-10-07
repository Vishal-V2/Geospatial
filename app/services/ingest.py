import json
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Feature, UploadedFile
from .measure import measure_geometry
from .readers import FileProcessingError, read_geofile


def process_file(db: Session, record: UploadedFile, saved_path: Path) -> UploadedFile:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            gdf = read_geofile(saved_path, Path(tmp))

        if len(gdf) > settings.max_features:
            raise FileProcessingError(f"Too many features (limit {settings.max_features}).")

        crs = gdf.crs
        crs_label = crs.to_string() if crs else None
        layers = gdf.pop("__layer")
        geojson = json.loads(gdf.to_json(drop_id=True))["features"]

        rows = []
        for i, (geom, gj) in enumerate(zip(gdf.geometry, geojson)):
            m = measure_geometry(geom, crs)
            rows.append(Feature(
                file_id=record.id, index=i, layer=layers.iloc[i],
                geometry_type=geom.geom_type if geom is not None else "None",
                geometry=gj["geometry"], crs=crs_label, properties=gj["properties"] or {},
                measurement_supported=m.supported, area_sq_m=m.area_sq_m,
                length_m=m.length_m, projected_crs=m.projected_crs, note=m.note,
            ))

        db.add_all(rows)
        record.crs, record.feature_count, record.status = crs_label, len(rows), "COMPLETED"
    except FileProcessingError as e:
        record.status, record.error = "FAILED", str(e)
    except Exception as e:  # noqa: BLE001 - catch-all to prevent service crash
        record.status, record.error = "FAILED", f"Could not read file: {e}"
    db.commit()
    db.refresh(record)
    return record