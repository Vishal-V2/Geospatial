import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set test database URL BEFORE importing app modules
os.environ["GEO_DATABASE_URL"] = "sqlite:///"


# ---- Database fixtures ----

from app.db import Base


@pytest.fixture(scope="session")
def test_engine():
    """Create a test engine with a temp file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    test_engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def clean_db(test_engine):
    """Rebuild tables for each test - full isolation, works regardless of commit()."""
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield


@pytest.fixture(autouse=True)
def override_get_db(test_engine):
    """Override FastAPI's get_db dependency for all tests."""
    from app.db import get_db
    from app.main import app
    
    SessionLocal = sessionmaker(bind=test_engine, autoflush=False)
    
    def get_test_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = get_test_db
    yield
    app.dependency_overrides.clear()


# ---- Shapefile fixtures ----

import zipfile

import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon


@pytest.fixture
def valid_shapefile_zip(tmp_path: Path) -> bytes:
    """Generate a valid Shapefile zip with .prj (EPSG:4326)."""
    gdf = gpd.GeoDataFrame({
        "name": ["Plot A", "Plot B"],
        "geometry": [
            Polygon([(77.20, 28.60), (77.21, 28.60), (77.21, 28.61), (77.20, 28.61)]),
            Polygon([(77.22, 28.62), (77.23, 28.62), (77.23, 28.63), (77.22, 28.63)])
        ]
    }, crs="EPSG:4326")

    shp_dir = tmp_path / "shapefile"
    shp_dir.mkdir()
    gdf.to_file(shp_dir / "test.shp")

    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in shp_dir.iterdir():
            zf.write(f, f.name)

    return zip_path.read_bytes()


@pytest.fixture
def invalid_shapefile_zip(tmp_path: Path) -> bytes:
    """Generate a Shapefile zip WITHOUT .prj (missing CRS)."""
    gdf = gpd.GeoDataFrame({
        "geometry": [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])]
    })
    gdf.crs = None  # No CRS assigned

    shp_dir = tmp_path / "shapefile"
    shp_dir.mkdir()
    gdf.to_file(shp_dir / "test.shp")

    # Explicitly remove .prj if created
    prj_path = shp_dir / "test.prj"
    if prj_path.exists():
        prj_path.unlink()

    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in shp_dir.iterdir():
            zf.write(f, f.name)

    return zip_path.read_bytes()


@pytest.fixture
def corrupt_zip() -> bytes:
    """Invalid/truncated zip file."""
    return b"PK\x03\x04" + b"\x00" * 100


@pytest.fixture
def zip_slip_zip(tmp_path: Path) -> bytes:
    """Zip with path traversal attempt."""
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../evil.txt", "bad")
    return evil.read_bytes()


@pytest.fixture
def no_shp_zip(tmp_path: Path) -> bytes:
    """Valid zip with only .dbf/.shx, no .shp."""
    z = tmp_path / "empty.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("test.dbf", b"dummy")
    return z.read_bytes()


@pytest.fixture
def mixed_geometry_zip(tmp_path: Path) -> bytes:
    """Zip containing three separate shapefiles: polygon, line, point."""
    # Create three separate shapefiles in subdirectories
    poly_dir = tmp_path / "poly"
    poly_dir.mkdir()
    poly_gdf = gpd.GeoDataFrame({
        "name": ["Plot A"],
        "geometry": [Polygon([(77.20, 28.60), (77.21, 28.60), (77.21, 28.61), (77.20, 28.61)])]
    }, crs="EPSG:4326")
    poly_gdf.to_file(poly_dir / "poly.shp")

    line_dir = tmp_path / "line"
    line_dir.mkdir()
    line_gdf = gpd.GeoDataFrame({
        "name": ["Road"],
        "geometry": [LineString([(77.20, 28.60), (77.22, 28.62)])]
    }, crs="EPSG:4326")
    line_gdf.to_file(line_dir / "line.shp")

    point_dir = tmp_path / "point"
    point_dir.mkdir()
    point_gdf = gpd.GeoDataFrame({
        "name": ["Gate"],
        "geometry": [Point(77.205, 28.605)]
    }, crs="EPSG:4326")
    point_gdf.to_file(point_dir / "point.shp")

    # Zip all three together
    zip_path = tmp_path / "mixed.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for d in [poly_dir, line_dir, point_dir]:
            for f in d.iterdir():
                # Use relative path from tmp_path
                arcname = f.relative_to(tmp_path)
                zf.write(f, arcname)

    return zip_path.read_bytes()
