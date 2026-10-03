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
- plotly
- folium
- streamlit-folium

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

Run the Streamlit placeholder:

```bash
streamlit run app.py
```

## Cross-platform note

Team members using Windows, Linux, or Intel-based macOS should recreate the environment from `environment.yml`. They should not assume that binary dependencies or exact builds from the Apple Silicon reference environment are portable to their system.
