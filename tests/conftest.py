import zipfile
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Polygon, LineString
import pytest


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