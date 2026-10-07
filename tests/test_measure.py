from shapely.geometry import GeometryCollection, LineString, Point, Polygon

from app.services.crs import utm_epsg
from app.services.measure import measure_geometry


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
    # Short line straddling the 43/44 boundary at 78°E, at 28°N
    line = LineString([(77.9, 28.0), (78.1, 28.0)])
    m = measure_geometry(line, "EPSG:4326")
    assert m.supported
    assert m.length_m is not None
    assert m.length_m > 0
    assert m.projected_crs is not None
    assert m.projected_crs.startswith("EPSG:326")

    # Compare to geodesic within 0.5%
    from pyproj import Geod
    GEOD = Geod(ellps="WGS84")
    geod_len = GEOD.line_length([77.9, 78.1], [28.0, 28.0])
    rel_error = abs(m.length_m - geod_len) / geod_len
    assert rel_error < 0.005, f"UTM length error {rel_error:.3%} vs geodesic (UTM={m.length_m:.0f}, geod={geod_len:.0f})"


def test_polar_linestring_geodesic():
    """LineString in polar region (lat >= 84) uses geodesic length."""
    # Line at 85°N
    line = LineString([(0.0, 85.0), (1.0, 85.0)])
    m = measure_geometry(line, "EPSG:4326")
    assert m.supported
    assert m.length_m is not None
    assert m.length_m > 0
    # Should use geodesic, not UTM
    assert m.projected_crs == "Geodesic (WGS84)"

    # Compare to geodesic within 0.5%
    from pyproj import Geod
    GEOD = Geod(ellps="WGS84")
    geod_len = GEOD.line_length([0.0, 1.0], [85.0, 85.0])
    rel_error = abs(m.length_m - geod_len) / geod_len
    assert rel_error < 0.005, f"Geodesic length error {rel_error:.3%} vs geodesic (got={m.length_m:.0f}, geod={geod_len:.0f})"


def test_bowtie_polygon_repair():
    """Self-intersecting (bow-tie) polygon is repaired and measured."""
    # Bow-tie: self-intersecting quadrilateral
    bowtie = Polygon([(0, 0), (1, 1), (0, 1), (1, 0)])
    assert not bowtie.is_valid
    m = measure_geometry(bowtie, "EPSG:4326")
    assert m.supported
    assert m.area_sq_m is not None
    assert m.area_sq_m > 0
    assert m.note is not None
    assert "repaired" in m.note.lower()


def test_polygon_repair_yields_nothing():
    """Degenerate polygon (collinear points) becomes LineString after repair -> unsupported."""
    # Three collinear points
    degenerate = Polygon([(0, 0), (1, 1), (2, 2)])
    m = measure_geometry(degenerate, "EPSG:4326")
    assert not m.supported
    assert m.note is not None
    assert "polygonal" in m.note.lower() or "no polygonal" in m.note.lower()
