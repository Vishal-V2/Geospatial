from dataclasses import dataclass
from shapely.geometry.base import BaseGeometry
from pyproj import CRS
from .crs import pick_projected_crs, reproject

AREA_TYPES = {"Polygon", "MultiPolygon"}
LENGTH_TYPES = {"LineString", "MultiLineString"}


@dataclass
class Measurement:
    supported: bool
    area_sq_m: float | None = None
    length_m: float | None = None
    projected_crs: str | None = None
    note: str | None = None


def measure_geometry(geom: BaseGeometry | None, src_crs: CRS | str) -> Measurement:
    if geom is None or geom.is_empty:
        return Measurement(False, note="Empty or missing geometry.")
    gtype = geom.geom_type

    if gtype in ("Point", "MultiPoint"):
        return Measurement(False, note="No measurement defined for points.")
    if gtype not in AREA_TYPES | LENGTH_TYPES:
        return Measurement(False, note=f"Unsupported geometry type: {gtype}.")

    try:
        epsg = pick_projected_crs(geom, src_crs)
        projected = reproject(geom, src_crs, epsg)
    except Exception as exc:
        return Measurement(False, note=f"Reprojection failed: {exc}")

    label = f"EPSG:{epsg}"
    if gtype in AREA_TYPES:
        return Measurement(True, area_sq_m=projected.area, projected_crs=label)
    return Measurement(True, length_m=projected.length, projected_crs=label)