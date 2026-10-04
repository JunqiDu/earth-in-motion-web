# Earth in Motion Web App

A Python-based geospatial and remote-sensing prototype for detecting and visualizing environmental change in Canada using RADARSAT Constellation Mission (RCM) and supporting Earth observation data.

This project was developed for Mission Accepted Space Hackathon 2026, Challenge 3: **Earth in Motion: Tracking Canada's Changing Landscape**. The final case study follows seven discrete December 2025 Fraser Valley / Lower Fraser RCM-derived flood observations and connects the mapped change to potential infrastructure, community, and Agricultural Land Reserve exposure.

## Technology stack

- Python 3.12 and Conda
- JupyterLab for data discovery and exploratory analysis
- Rasterio, rioxarray, xarray, GeoPandas, Shapely, and pyproj for geospatial processing
- pystac-client and stackstac for STAC-based data access
- Streamlit, PyDeck/DeckGL, and Plotly for the offline web dashboard

## Repository structure

```text
.
├── app.py              # Final six-section Streamlit dashboard
├── notebooks/          # Executed Phase 1–5 research notebooks
├── data/processed/phase4/ # Canonical seven-observation temporal contract and audit
├── data/processed/phase5/ # Dashboard-ready exposure CSV/GeoJSON and compatibility views
├── docs/               # Planning and technical documentation
└── assets/phase5/      # Retained analytical exports for provenance and comparison
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

Start JupyterLab for research notebooks:

```bash
jupyter lab
```

## Run the dashboard

From the repository root:

```bash
conda activate space-hackathon-2026
streamlit run app.py
```

Then open <http://localhost:8501>. The dashboard reads only committed local processed outputs during normal startup; it does not download satellite scenes, query EODMS, contact OSM, load an online basemap, or rerun the research workflow.

## Final workflow

### Stage 1 — Research & Method Selection (Phase 3B frozen)

We obtained 11 accessible RCM Level-1 GRD products, then calibrated and
terrain-corrected the five acquisitions matched to NRCan EGS. Independent
open-water classification progressed from SAR thresholds and a Lee comparison
to multisource constraints and historical-label, scene-specific Random Forests.
EGS class 2 was used for evaluation, never RF training. Final RF v2 achieved
median IoU **0.353** against original EGS directly rasterized to 30 m (**0.409**
against the legacy reference). It did not meet the unchanged GO gate:
**FINAL EXPERIMENTAL FAIL**. Research is closed, not awaiting another refinement.
The operational EGS extent remains the final prototype source; the Level-1
methods and their failures remain auditable research evidence.

In our accessible Level-1 dataset, the finest available RCM imagery was 16 m;
ScanSAR products were 30 m. Some operational EGS timeline products used finer
5 m acquisitions whose matching Level-1 data was not in our local research set.
Resolution is one plausible contributor, not a proven explanation for the gap.

See [final 3B record](docs/phase3b.md), [method research](docs/phase3b_method_research.md),
and the finalized `notebooks/03b_level1_validation.ipynb`. To view the frozen
summary without retraining or downloading:

```bash
python scripts/phase3b_final.py
python scripts/phase3b_check_final.py
```

### Stage 2 — Translation & Impact Communication

The selected RCM-derived EGS workflow communicates temporal flood evolution,
regional hydrology, recovery, potential road/bridge-tagged-way exposure,
ALR-designation overlap, community context, evidence and limitations. Phase 3B
has not replaced Phase 4/5 or the Dashboard contracts.

```text
Phase 1–4 research, validation, and temporal audit
    -> canonical Phase 4 observation contract
    -> compact Phase 5 exposure handoff
    -> Phase 6 Streamlit dashboard
```

The dashboard follows one question per section:

- **Overview:** what changed and how the result was produced at a high level;
- **Detect:** where meaningful local water expansion occurred, including G042 and G015;
- **Map:** a paused-by-default seven-step local acquisition player, followed by the complete interactive spatial explorer;
- **Monitor:** the seven discrete acquisitions in regional two-pulse context; the committed Phase 4 contract is the scientific source of truth;
- **Impact:** potential road, bridge-tagged-way, ALR-designation, and community context;
- **Evidence & Method:** validation, official sources, limitations, and claim boundaries.

Raw satellite data and general generated outputs are intentionally excluded from Git. `data/processed/phase4/event_observations.csv`, `rcm_stage_alignment.csv`, and the seven-frame GeoJSON are the Dashboard temporal source of truth. The Phase 5 `event_trajectory.csv` and `temporal_series.csv` files remain generated compatibility views, but Map and Monitor no longer depend on them at startup. Four PNG maps remain under `assets/phase5/` as provenance exports and are not required at startup.

The common 20 m grid standardizes spatial accounting but does not normalize different RCM beam modes, source resolutions, viewing directions, radiometry, classifier channels, or independently processed EGS products. The seven observations are therefore an acquisition sequence—not a daily hydrograph, continuous interpolation, or measured flood peak. Committed WaterOffice 5-minute station values provide regional context for a first hydrologic pulse, an inter-pulse low, and a second hydrologic pulse; they do not validate individual pixels. Endpoint change is reported as 35.44 ha gross recession from the initial footprint and 33.28 ha net decline, with 19.48 ha persistence and 2.16 ha final-only mapping.

## Status

Phases 1–5 and the current Phase 6 prototype are complete. The Map player is paused by default: drag its acquisition-progress control to inspect a stored observation, or click **Play one pass** to advance through OBS01–OBS07 exactly once and stop. It never interpolates dates or requests remote data. The scientific handoff distinguishes the canonical discrete-acquisition record from the Dashboard compatibility layer. Intersections and proximity are described as potential exposure only; the project does not claim confirmed damage, flood depth, population impact, crop loss, a satellite-derived flood peak, or climate causation.
