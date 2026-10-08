import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Feature, UploadedFile
from ..schemas import FileOut, MeasurementsResponse
from ..services.ingest import process_file

router = APIRouter(prefix="/api/files", tags=["files"])
ALLOWED = {".zip", ".kml"}


@router.post("/", response_model=FileOut, status_code=201)
def upload(file: UploadFile = File(...), db: Session = Depends(get_db)):  # noqa: B008
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(415, "Only .zip (Shapefile) and .kml are supported.")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"upload{suffix}"
        size, limit = 0, settings.max_upload_mb * 1024 * 1024
        with open(path, "wb") as out:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB.")
                out.write(chunk)

        record = UploadedFile(filename=file.filename)
        db.add(record)
        db.commit()
        record = process_file(db, record, path)

    return record


def _get_or_404(db: Session, file_id: str) -> UploadedFile:
    rec = db.get(UploadedFile, file_id)
    if not rec:
        raise HTTPException(404, "File not found.")
    return rec


@router.get("/{file_id}/", response_model=FileOut)
def file_info(file_id: str, db: Session = Depends(get_db)):  # noqa: B008
    return _get_or_404(db, file_id)


@router.get("/{file_id}/measurements/", response_model=MeasurementsResponse)
def measurements(
    file_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    include_geometry: bool = Query(True, description="Set to false to omit geometry; the geometry field will be null"),
    db: Session = Depends(get_db),  # noqa: B008
):
    file_rec = _get_or_404(db, file_id)
    if file_rec.status != "COMPLETED":
        raise HTTPException(409, f"File status is {file_rec.status}: {file_rec.error or 'processing not complete'}")

    q = select(Feature).where(Feature.file_id == file_id).order_by(Feature.index)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.limit(limit).offset(offset)).all()

    if not include_geometry:
        results = []
        for row in rows:
            results.append({
                "index": row.index,
                "layer": row.layer,
                "geometry_type": row.geometry_type,
                "geometry": None,
                "crs": row.crs,
                "properties": row.properties,
                "measurement_supported": row.measurement_supported,
                "area_sq_m": row.area_sq_m,
                "length_m": row.length_m,
                "projected_crs": row.projected_crs,
                "note": row.note,
            })
        return MeasurementsResponse(
            file_id=file_id,
            total=total,
            limit=limit,
            offset=offset,
            results=results,
        )

    return MeasurementsResponse(file_id=file_id, total=total, limit=limit, offset=offset, results=rows)