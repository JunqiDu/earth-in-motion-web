# Decision Log

## 2026-10-03 — Initial technical foundation

- Use **Python** as the main project language because the planned geospatial, raster, notebook, and dashboard workflows share a mature Python ecosystem.
- Use **JupyterLab** for exploratory data discovery and analysis.
- Use **Streamlit** for the hackathon web prototype.
- Use **Conda** with `conda-forge` for environment and native geospatial dependency management.
- Target **Python 3.12** for the shared development environment.
- Exclude raw and processed satellite data and generated outputs from Git; retain only directory placeholders.

## 2026-10-03 — Phase 1 RCM feasibility path

- Use **Folly Lake, Colchester County, Nova Scotia** as the temporary feasibility AOI because it is inland, has a clear shoreline, and has multiple valid RCM-ARD acquisitions. This does not select the final study area or phenomenon.
- Use the official **EODMS STAC API** for discovery. Query `RCMImageProducts` for broad Level-1 availability and `rcm-ard` for directly readable public CEOS-ARD assets.
- Use **windowed HTTP reads from Cloud-Optimized GeoTIFFs** for feasibility so that no complete satellite scene needs to be downloaded.
- Defer authenticated Level-1 downloads. Product ZIP assets require an EODMS bearer token, while the public ARD path is sufficient for the current phase.
