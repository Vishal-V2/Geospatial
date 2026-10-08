import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio

from ..config import settings


class FileProcessingError(Exception):
    """Raised for user-correctable problems (maps to HTTP 422)."""


# GDAL KML boilerplate keys to filter out (denylist) — match exact casing from GDAL
# Keep Name and description as they are meaningful KML properties
_KML_BOILERPLATE_KEYS = {
    "tessellate", "extrude", "visibility", "drawOrder", "altitudeMode",
    "icon", "timestamp", "begin", "end", "id"
}


def safe_extract(zip_path: Path, dest: Path) -> None:
    limit = settings.max_unzipped_mb * 1024 * 1024
    try:
        with zipfile.ZipFile(zip_path) as zf:
            total = sum(i.file_size for i in zf.infolist())
            if total > limit:
                raise FileProcessingError("Zip contents exceed the allowed size.")
            for member in zf.infolist():
                target = (dest / member.filename).resolve()
                if not target.is_relative_to(dest.resolve()):
                    raise FileProcessingError("Zip contains unsafe paths.")
            zf.extractall(dest)
    except zipfile.BadZipFile:
        raise FileProcessingError("Invalid zip archive.")


def _read_all_layers(path: Path) -> gpd.GeoDataFrame:
    frames = []
    for layer_name, _geom in pyogrio.list_layers(path):
        gdf = pyogrio.read_dataframe(path, layer=layer_name)
        if len(gdf):
            # Drop KML boilerplate columns (properties are separate columns in GDAL KML)
            boilerplate_cols = [c for c in gdf.columns if c in _KML_BOILERPLATE_KEYS]
            gdf = gdf.drop(columns=boilerplate_cols)
            gdf["__layer"] = layer_name
            frames.append(gdf)
    if not frames:
        raise FileProcessingError("No features found in file.")
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)


def read_geofile(path: Path, workdir: Path) -> gpd.GeoDataFrame:
    suffix = path.suffix.lower()
    if suffix == ".kml":
        try:
            gdf = _read_all_layers(path)
        except Exception as exc:
            raise FileProcessingError("Could not parse KML file") from exc
        if gdf.crs is None:
            gdf = gdf.set_crs(4326)
        return gdf
    if suffix == ".zip":
        safe_extract(path, workdir)
        shps = sorted(workdir.rglob("*.shp"))
        if not shps:
            raise FileProcessingError("Zip does not contain a .shp file.")
        frames = []
        for shp in shps:
            g = pyogrio.read_dataframe(shp)
            if g.crs is None:
                raise FileProcessingError(f"{shp.name} has no CRS (.prj missing).")
            g["__layer"] = shp.stem
            frames.append(g.to_crs(frames[0].crs) if frames else g)
        return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
    raise FileProcessingError("Unsupported file type. Upload a .zip (Shapefile) or .kml.")