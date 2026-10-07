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


def test_polygon_area_accuracy_vs_geodesic():
    """UTM area should be within 0.5% of geodesic area for a reasonably-sized polygon."""
    from pyproj import Geod
    GEOD = Geod(ellps="WGS84")

    # ~1km square near Delhi (UTM zone 43N)
    poly = Polygon([(77.20, 28.60), (77.21, 28.60), (77.21, 28.61), (77.20, 28.61)])
    m = measure_geometry(poly, "EPSG:4326")
    assert m.supported

    # Geodesic area
    geod_area, _ = GEOD.geometry_area_perimeter(poly)
    geod_area = abs(geod_area)

    # Relative error
    rel_error = abs(m.area_sq_m - geod_area) / geod_area
    assert rel_error < 0.005, f"UTM area error {rel_error:.3%} vs geodesic (UTM={m.area_sq_m:.0f}, geod={geod_area:.0f})"


def test_multi_zone_line_crossing_boundary():
    """Line crossing UTM zone boundary should still return a length measurement."""
    # Line from ~77°E to ~84°E at ~28°N crosses zones 43→44→45
    # Use a shorter line that crosses zone boundary: zone 43 ends at 78°E, zone 44 starts
    line = LineString([(77.9, 28.6), (78.2, 28.6)])  # crosses 78°E boundary
    m = measure_geometry(line, "EPSG:4326")
    assert m.supported
    assert m.length_m is not None
    assert m.length_m > 0
    # Should use UTM zone 43 or 44 (whichever centroid falls in)
    assert m.projected_crs is not None
    assert m.projected_crs.startswith("EPSG:326")