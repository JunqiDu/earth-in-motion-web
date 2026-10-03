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

## 2026-10-03 — Phase 4 final event and analysis route

- Select the **December 2025 Fraser Valley / Lower Fraser flood** as the final real-world case, using a Chilliwack-area AOI. The July 2023 Nova Scotia flood was rejected after the tested official-impact AOIs produced no usable event-period RCM records; the May 2025 Central Ottawa case was rejected after its quantitative change failed the empirical benchmark and independent-overlap test.
- Fix the Phase 4 AOI at EPSG:32610 bounds `(563960, 5443240, 569960, 5449240)`, approximately WGS84 `(-122.123101, 49.138657, -122.039809, 49.191968)`. This 6 km × 6 km area has complete common coverage from seven EGS observations and strong public-ARD coverage before/after the event.
- Use seven openly accessible **NRCan EGS RCM-derived flood products** from 12–21 December as the main event sequence. Use public CEOS-ARD mosaics from 8 November and 7 January as real outer RCM brackets. Do not require authenticated Level-1 downloads for the reproducible prototype.
- Preserve a fixed EPSG:32610 **20 m analysis grid**. Rasterize EGS categorical vectors directly; use nearest-neighbour for masks/classes and mode for categorical optical aggregation. Use bilinear interpolation only for continuous ARD RR and geometry-support layers.
- Keep `data_mask == 1` as the only valid CEOS-ARD class and retain platform/orbit/mode/polarization, source CRS/resolution/transform, local incidence angle, and gamma/sigma diagnostics.
- Apply `RR < -17.314 dB` only to the same CEOS-ARD representation used in Phase 3. Do not transfer the threshold to EGS semantic vectors or Level-1 GRD.
- Use a fixed **1 km grid** for localized change. Treat 3.20%, 5.88%, and 4.88% only as empirical method-noise context from Folly Lake. A grid above 5.88 percentage points is a stronger candidate for corroboration, not a universal flood decision or a formal statistically significant result.
- Prefer a Lower Fraser baseline made from multiple comparable pre-event observations when such data become available. The already-discovered inputs contain only one pre-event RCM-ARD acquisition and one pre-event Sentinel-2 observation, neither semantically interchangeable with EGS. Phase 4 therefore retains the EGS permanent-water class as a provisional local semantic baseline and does not manufacture a multi-date frequency model.
- Define the event anomaly as EGS flood water appearing outside that local baseline, interpreted jointly with spatial continuity, temporal evolution, independent EO/official evidence, and impact context. Temporal recovery/persistence labels do not depend on crossing the Folly Lake value.
- Classify the case as a **recovering flood with localized residual/persistent expansion**: EGS open-water flood declines from 54.92 ha on 12 December to 21.64 ha on 21 December, while two of 49 grid cells exceed the local benchmark.
- Use Sentinel-2 only as independent recovery-period evidence because event-window optical coverage is cloud-obstructed. Retain Sentinel-1 metadata coverage but do not force requester-pays Level-1 measurements into an anonymously reproducible analysis.
- Describe road/bridge intersections as **intersecting** or **potentially exposed**. Do not claim satellite overlap proves damage, closure, or flood depth.
- When Phase 5 is started in a later task, focus impact analysis on the two cells above the control-site context while keeping provenance and uncertainty visible.
