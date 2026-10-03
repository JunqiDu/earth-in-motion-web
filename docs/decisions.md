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

## 2026-10-03 — Phase 2 provisional water-measurement baseline

- Use **RR** as the working Phase 3 backscatter asset because it produced stronger reference-date water/land separation and lower eight-date area variability than RL at Folly Lake.
- Use a **provisional RR threshold of -17.31 dB**, derived as the midpoint between the reference water-sample upper quartile and land-sample lower quartile. This is an exploratory threshold, not a validated universal value.
- Retain only **8-connected thresholded components intersecting a fixed interior-water seed** within the documented analysis rectangle. This suppresses unrelated dark patches while keeping the rule reproducible and explainable.
- Treat the Phase 2 area series as a stability test only. Phase 3 preprocessing/alignment and independent reference validation remain required before interpreting change.

## 2026-10-03 — Phase 3 alignment and independent validation

- Preserve the native **EPSG:32620, 20 m RCM grid**. All eight tested AOI windows have identical affine origin, extent, and shape, so RCM reprojection would add unnecessary interpolation.
- Treat only CEOS-ARD data-mask **code 1 as analysis-valid**. Exclude invalid, layover, shadow, and combined layover-shadow values before classification or validation.
- Use **same-day Sentinel-2 L2A NDWI** as the primary independent EO comparison. Apply source scale/offset, exclude invalid SCL classes, calculate NDWI on the native 10 m spectral grid, and aggregate the categorical result to 20 m with mode resampling.
- Use the **Nova Scotia Hydrographic Network Folly Lake polygon** as a second, authoritative nominal geometry check, not as exact 2025 shoreline truth.
- Accept the RCM RR method as a **conditional relative-change baseline** because the same-day Sentinel comparison gives precision 0.864, recall 0.906, F1 0.885, IoU 0.794, and +4.88% area error.
- Do not use the current method for small absolute shoreline claims. Phase 4 must compare candidate changes with the Phase 2 stability/sensitivity envelope, retain platform metadata, and seek more independent optical dates.
- Continue to use Folly Lake only as a calibration/control site. Phase 3 does not support environmental or climate attribution.
