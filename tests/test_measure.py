import pytest
from shapely.geometry import Polygon, LineString, Point, GeometryCollection
from app.services.measure import measure_geometry
from app.services.crs import utm_epsg


def test_utm_zone_selection():
    assert utm_epsg(77.2, 28.6) == 32643
    assert utm_epsg(-58.4, -34.6) == 32721


def test_polygon_area_reasonable():
    poly = Polygon([(77.20, 28.60), (77.21, 28.60), (77.21, 28.61), (77.20, 28.61)])
    m = measure_geometry(poly, "EPSG:4326")
    assert m.supported and 1.0e6 < m.area_sq_m < 1.3e6


def test_line_length():
    m = measure_geometry(LineString([(77.20, 28.60), (77.22, 28.62)]), "EPSG:4326")
    assert m.supported and 2_500 < m.length_m < 3_500


def test_point_not_measured():
    assert not measure_geometry(Point(77.2, 28.6), "EPSG:4326").supported


def test_unsupported_type_graceful():
    m = measure_geometry(GeometryCollection([Point(0, 0)]), "EPSG:4326")
    assert not m.supported and "Unsupported" in m.note