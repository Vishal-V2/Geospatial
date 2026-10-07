from functools import lru_cache

import numpy as np
import shapely
from pyproj import CRS, Geod, Transformer
from shapely.geometry.base import BaseGeometry

EQUAL_AREA_FALLBACK = 6933

GEOD = Geod(ellps="WGS84")


@lru_cache(maxsize=256)
def _transformer(src: str, dst: str) -> Transformer:
    return Transformer.from_crs(src, dst, always_xy=True)


def reproject(geom: BaseGeometry, src: CRS | str, dst: CRS | str | int) -> BaseGeometry:
    src, dst = CRS.from_user_input(src).to_string(), CRS.from_user_input(dst).to_string()
    if src == dst:
        return geom
    t = _transformer(src, dst)

    def _apply(coords: np.ndarray) -> np.ndarray:
        x, y = t.transform(coords[:, 0], coords[:, 1])
        return np.column_stack([x, y])

    return shapely.transform(geom, _apply)


def utm_epsg(lon: float, lat: float) -> int:
    if lat >= 84 or lat <= -80:
        return EQUAL_AREA_FALLBACK
    zone = min(max(int((lon + 180) // 6) + 1, 1), 60)
    return (32600 if lat >= 0 else 32700) + zone


def pick_projected_crs(geom: BaseGeometry, src_crs: CRS | str) -> int:
    wgs = reproject(geom, src_crs, 4326)
    c = wgs.centroid
    return utm_epsg(c.x, c.y)


def geodesic_length_m(geom: BaseGeometry, src_crs: CRS | str) -> float:
    """Compute length in meters using geodesic (for polar regions)."""
    wgs = reproject(geom, src_crs, 4326)
    if wgs.geom_type == "LineString":
        lons, lats = zip(*wgs.coords)
        return GEOD.line_length(lons, lats)
    elif wgs.geom_type == "MultiLineString":
        total = 0.0
        for line in wgs.geoms:
            lons, lats = zip(*line.coords)
            total += GEOD.line_length(lons, lats)
        return total
    raise ValueError("Not a LineString/MultiLineString")