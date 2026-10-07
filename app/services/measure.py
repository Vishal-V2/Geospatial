from dataclasses import dataclass

from pyproj import CRS
from shapely import is_valid, make_valid
from shapely.geometry.base import BaseGeometry

from .crs import EQUAL_AREA_FALLBACK, geodesic_length_m, pick_projected_crs, reproject

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
    note_parts = []

    # Repair invalid polygons for measurement only
    if gtype in AREA_TYPES and not is_valid(geom):
        geom = make_valid(geom)
        note_parts.append("Geometry was invalid; repaired for measurement.")
        # If repair yields non-polygonal (e.g., GeometryCollection), extract polygons
        if geom.geom_type != "Polygon" and geom.geom_type != "MultiPolygon":
            # Try to get largest polygon part
            if geom.geom_type == "GeometryCollection":
                polys = [g for g in geom.geoms if g.geom_type in AREA_TYPES]
                if not polys:
                    return Measurement(False, note="Invalid polygon; repair yielded no polygonal area.")
                geom = max(polys, key=lambda p: p.area)
                note_parts.append("Used largest polygonal part after repair.")
            elif geom.geom_type not in AREA_TYPES:
                return Measurement(False, note="Invalid polygon; repair yielded no polygonal area.")

    if gtype in ("Point", "MultiPoint"):
        return Measurement(False, note="No measurement defined for points.")
    if gtype not in AREA_TYPES | LENGTH_TYPES:
        return Measurement(False, note=f"Unsupported geometry type: {gtype}.")

    try:
        epsg = pick_projected_crs(geom, src_crs)
        projected = reproject(geom, src_crs, epsg)
    except Exception as exc:  # noqa: BLE001 - catch-all for reprojection safety
        return Measurement(False, note=f"Reprojection failed: {exc}")

    label = f"EPSG:{epsg}"
    if gtype in AREA_TYPES:
        return Measurement(
            True,
            area_sq_m=projected.area,
            projected_crs=label,
            note="; ".join(note_parts) or None,
        )

    # LineString handling (with polar geodesic)
    if epsg == EQUAL_AREA_FALLBACK:
        length = geodesic_length_m(geom, src_crs)
        note = "Geodesic length (polar fallback)" + ("; " + "; ".join(note_parts) if note_parts else "")
        return Measurement(
            True,
            length_m=length,
            projected_crs="Geodesic (WGS84)",
            note=note or None,
        )

    return Measurement(
        True,
        length_m=projected.length,
        projected_crs=label,
        note="; ".join(note_parts) or None,
    )