# Earth in Motion Web App

A Python-based geospatial and remote-sensing prototype for detecting and visualizing environmental change in Canada using RADARSAT Constellation Mission (RCM) Earth observation data from EODMS.

This project is being developed for Mission Accepted Space Hackathon 2026, Challenge 3: **Earth in Motion: Tracking Canada's Changing Landscape**. Its goal is to explore a reproducible workflow for detecting, mapping, and monitoring landscape change and presenting the results in an accessible web application.

## Planned technology stack

- Python 3.12 and Conda
- JupyterLab for data discovery and exploratory analysis
- Rasterio, rioxarray, xarray, GeoPandas, Shapely, and pyproj for geospatial processing
- pystac-client and stackstac for STAC-based data access
- Streamlit, Plotly, Folium, and streamlit-folium for the web prototype

## Repository structure

```text
.
├── app.py              # Minimal Streamlit entry point
├── notebooks/          # Executed discovery, validation, and change-analysis notebooks
├── data/               # Local raw, processed, and output data
├── docs/               # Planning and technical documentation
└── assets/             # Static project assets
```

## Environment setup

Create the environment from the concise Conda definition:

```bash
conda env create --file environment.yml
conda activate space-hackathon-2026
```

If the environment already exists, synchronize it with:

```bash
conda env update --name space-hackathon-2026 --file environment.yml --prune
```

Register the Jupyter kernel when setting up a new machine:

```bash
python -m ipykernel install --user \
  --name space-hackathon-2026 \
  --display-name "Python 3.12 (Space Hackathon 2026)"
```

Start JupyterLab:

```bash
jupyter lab
```

Run the Streamlit placeholder:

```bash
streamlit run app.py
```

Raw satellite data and general generated outputs are intentionally excluded from Git. The small, reproducible Phase 5 handoff package under `data/processed/phase5/` and four reusable maps under `assets/phase5/` are retained; no source scenes or extracted archives are committed.

## Status

Phases 1–5 of the satellite and impact analysis are complete for the current prototype. The selected case is the December 2025 Fraser Valley / Lower Fraser flood. Phase 5 consolidates priority grids, road/bridge proximity, community and Agricultural Land Reserve context, official evidence, claims, limitations, and a compact Phase 6 handoff package. The Streamlit application remains a placeholder; no Phase 6 implementation has started.
