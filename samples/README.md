# Sample inputs

Small files for trying the API by hand. All data sits near lon 10.0, lat 50.0 (UTM zone 32N, `EPSG:32632`).

```bash
curl -F "file=@samples/01_polygons_only.zip" http://127.0.0.1:8000/api/files/
```

Values below are what the API returned when these files were uploaded. Areas and lengths differ from true
geodesic values by about 0.03-0.07% because of the UTM scale factor (see "Accuracy note" in the main README).

| File | Contents | Expected result |
|---|---|---|
| `01_polygons_only.zip` | 2 polygons | `COMPLETED`, areas 999,234.8 and 249,823.4 m² |
| `02_lines_only.zip` | 2 lines | `COMPLETED`, lengths of about 2,999 m and 2,120 m (from the equivalent KML) |
| `03_mixed_geometry.zip` | 3 shapefiles: polygon, line, point | `COMPLETED`, 3 features, the point has `measurement_supported: false` |
| `04_points_only_unsupported.zip` | 2 MultiPoints | `COMPLETED`, nothing measured, note on each feature |
| `05_invalid_polygon.zip` | self-intersecting "bowtie" plus a valid square | `COMPLETED`, bowtie measured after repair (398,434 m²) with a note |
| `06_no_prj_should_fail.zip` | shapefile without `.prj` | `FAILED`: "parcels.shp has no CRS (.prj missing)." |
| `07_projected_utm32n.zip` | same polygons as 01 in `EPSG:32632` | `COMPLETED`, `crs` is `EPSG:32632`, areas identical to 01 |
| `08_corrupt.zip` | not a real zip | `FAILED`: "Invalid zip archive." |
| `09_zip_without_shapefile.zip` | zip with only a text file | `FAILED`: "Zip does not contain a .shp file." |
| `10_zip_slip_attack.zip` | zip with a `../../` path | `FAILED`: "Zip contains unsafe paths." |
| `11_sample_mixed.kml` | 3 KML folders: polygons, lines, a point | `COMPLETED`, 5 features |
| `12_kml_invalid_polygon.kml` | bowtie plus a valid square | `COMPLETED`, bowtie repaired with a note |
| `13_kml_multigeometry_mixed.kml` | one placemark containing polygon + line + point | `COMPLETED`, returned as a `GeometryCollection`, not measured |
| `14_kml_malformed.kml` | truncated XML | `FAILED` with a generic parse error |
| `15_wrong_extension.txt` | wrong file type | HTTP `415`, no record created |

Files `01`-`14` return HTTP `201`; check the `status` field of the response.
