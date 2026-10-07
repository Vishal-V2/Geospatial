from functools import lru_cache
from pyproj import CRS, Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

EQUAL_AREA_FALLBACK = 6933


@lru_cache(maxsize=256)
def _transformer(src: str, dst: str) -> Transformer:
    return Transformer.from_crs(src, dst, always_xy=True)


def reproject(geom: BaseGeometry, src: CRS | str, dst: CRS | str | int) -> BaseGeometry:
    src, dst = CRS.from_user_input(src).to_string(), CRS.from_user_input(dst).to_string()
    return geom if src == dst else transform(_transformer(src, dst).transform, geom)


def utm_epsg(lon: float, lat: float) -> int:
    if lat >= 84 or lat <= -80:
        return EQUAL_AREA_FALLBACK
    zone = min(max(int((lon + 180) // 6) + 1, 1), 60)
    return (32600 if lat >= 0 else 32700) + zone


def pick_projected_crs(geom: BaseGeometry, src_crs: CRS | str) -> int:
    wgs = reproject(geom, src_crs, 4326)
    c = wgs.centroid
    return utm_epsg(c.x, c.y)