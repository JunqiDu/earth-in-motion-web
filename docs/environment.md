# Development Environment

## Reference environment

- Operating system: macOS
- Architecture: Apple Silicon (`arm64`)
- Conda environment: `space-hackathon-2026`
- Python: 3.12
- Jupyter kernel: `Python 3.12 (Space Hackathon 2026)`

## Major package groups

### Core / notebook

- jupyterlab
- ipykernel
- numpy
- pandas
- matplotlib

### Geospatial / raster

- rasterio
- rioxarray
- xarray
- geopandas
- shapely
- pyproj

### RCM / STAC

- pystac-client
- stackstac

### Dashboard

- streamlit
- pydeck
- plotly

## Common commands

Activate the environment:

```bash
conda activate space-hackathon-2026
```

Check that the expected interpreter is active:

```bash
python --version
python -c "import platform, sys; print(sys.executable); print(platform.machine())"
```

Launch JupyterLab:

```bash
jupyter lab
```

In JupyterLab, select **Kernel > Change Kernel > Python 3.12 (Space Hackathon 2026)** when the notebook is not already using that kernel.

Run the local dashboard:

```bash
streamlit run app.py
```

Scientific layers use committed CSV and GeoJSON files. No satellite download, model training, or exposure query runs at dashboard startup. The restored CARTO/OpenStreetMap basemap does request online map resources and needs internet for geographic context. Do not describe the final interface as fully offline.

SNAP 14 is needed only to reproduce Level-1 preprocessing, not to view the final dashboard. Phase 3B is frozen as FINAL EXPERIMENTAL FAIL; environment setup does not authorize another training or processing run. See [Phase 3B](phase3b.md).

Read-only final checks:

```bash
python scripts/phase45_validate.py
python -m unittest discover -s tests -p test_dashboard.py -v
```

The [dashboard guide](dashboard.md) explains the final seven pages and a short demo sequence.

## Cross-platform note

Team members using Windows, Linux, or Intel-based macOS should recreate the environment from `environment.yml`. They should not assume that binary dependencies or exact builds from the Apple Silicon reference environment are portable to their system.
