import shutil
import tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..db import get_db
from ..config import settings
from ..models import UploadedFile, Feature
from ..schemas import FileOut, MeasurementsResponse
from ..services.ingest import process_file

router = APIRouter(prefix="/api/files", tags=["files"])
ALLOWED = {".zip", ".kml"}


@router.post("/", response_model=FileOut, status_code=201)
def upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
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

    if record.status == "FAILED":
        raise HTTPException(422, record.error)
    return record


def _get_or_404(db: Session, file_id: str) -> UploadedFile:
    rec = db.get(UploadedFile, file_id)
    if not rec:
        raise HTTPException(404, "File not found.")
    return rec


@router.get("/{file_id}/", response_model=FileOut)
def file_info(file_id: str, db: Session = Depends(get_db)):
    return _get_or_404(db, file_id)


@router.get("/{file_id}/measurements/", response_model=MeasurementsResponse)
def measurements(
    file_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    _get_or_404(db, file_id)
    q = select(Feature).where(Feature.file_id == file_id).order_by(Feature.index)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.limit(limit).offset(offset)).all()
    return MeasurementsResponse(file_id=file_id, total=total, limit=limit, offset=offset, results=rows)