import os
import tempfile
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# Set test database URL BEFORE importing app modules
os.environ["GEO_DATABASE_URL"] = "sqlite:///"


@pytest.fixture(scope="session")
def test_db_path():
    """Session-scoped temp SQLite file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture(scope="session")
def test_engine(test_db_path):
    engine = create_engine(
        f"sqlite:///{test_db_path}",
        connect_args={"check_same_thread": False},
    )
    from app.db import Base
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Fresh session per test, rolls back after."""
    SessionLocal = sessionmaker(bind=test_engine, autoflush=False)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture(autouse=True)
def override_get_db(test_db):
    """Override FastAPI's get_db dependency for all tests."""
    from app.main import app
    from app.db import get_db
    app.dependency_overrides[get_db] = lambda: test_db
    yield
    app.dependency_overrides.clear()


# ---- Shapefile fixtures ----

import zipfile
import geopandas as gpd
from shapely.geometry import Polygon, LineString


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