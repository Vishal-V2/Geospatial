from pydantic import BaseModel, ConfigDict


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    feature_count: int
    crs: str | None
    status: str
    error: str | None = None


class MeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    index: int
    layer: str | None
    geometry_type: str
    geometry: dict | None
    crs: str | None
    properties: dict
    measurement_supported: bool
    area_sq_m: float | None = None
    length_m: float | None = None
    projected_crs: str | None = None
    note: str | None = None


class MeasurementsResponse(BaseModel):
    file_id: str
    total: int
    limit: int
    offset: int
    results: list[MeasurementOut]