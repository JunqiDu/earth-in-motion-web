# Analysis Method

This document records the Phase 2 RCM backscatter exploration and Phase 3 preprocessing/validation work confirmed on 2026-10-03. The method is a feasibility baseline for Folly Lake, not a universal water classifier or evidence of environmental change.

## Confirmed observations

### Comparable acquisition subset

Eight independent RCM CEOS-ARD acquisition groups were included:

| Date | Platform | Selected STAC item |
| --- | --- | --- |
| 2025-07-14 | RCM3 | `41d2b89c-cd7a-496b-aaac-8d7326c70728` |
| 2025-07-26 | RCM3 | `4a51a899-0b2d-41c6-9948-29d7c0dd8ffc` |
| 2025-09-12 | RCM3 | `8efbb31b-2951-4cb5-8d35-05121f1de930` |
| 2025-10-14 | RCM2 | `df8f9ed0-f8d6-4043-8ec0-be40128be006` |
| 2025-10-26 | RCM2 | `131e7580-fdb3-4897-b374-e4fc8330141c` |
| 2025-11-07 | RCM2 | `73a52ca6-f8ac-4d82-a81b-08a23084460a` |
| 2026-07-05 | RCM2 | `4b387ee1-5623-46e6-8001-811d4074986b` |
| 2026-08-02 | RCM3 | `d5d2c686-1c84-4304-83fd-4db5d9a9a8d8` |

All eight are Level-2 MLC, CEOS ARD `NRB - POL`, `Medium Resolution 30m`, relative orbit 37, descending/right-looking, EPSG:32620, and 20 m output spacing. The tested windows share one grid. Mean local incidence angle over the analysis rectangle ranges only from approximately 27.971° to 27.985°.

Two extra catalogue records on 2025-10-26 and 2025-11-07 were overlapping records from the same satellite/orbit acquisitions. They were excluded from temporal counting, not treated as additional observations or bad dates.

### Reproducible sample regions

All exploratory geometries use EPSG:32620:

- water sample: `(457220, 5042800, 457340, 5043300)`, placed inside the western lake lobe;
- land sample: `(457850, 5043250, 457970, 5043900)`, placed east of the visible shoreline;
- analysis rectangle: `(457000, 5041900, 458000, 5044100)`.

The water and land samples avoid obvious shoreline mixing in the 2025-07-14 reference image. They were selected from SAR imagery and are not independent ground truth.

### Backscatter preparation

RR and RL COG windows are read remotely. Positive linear backscatter values are converted to decibels using:

`dB = 10 × log10(linear backscatter)`

Nodata, non-finite, and non-positive values are excluded.

### RR versus RL separation

For the 2025-07-14 reference date:

| Asset | Water median | Land median | Median gap | Standardized separation |
| --- | ---: | ---: | ---: | ---: |
| RR | -22.51 dB | -11.74 dB | 10.77 dB | 13.32 |
| RL | -15.24 dB | -8.29 dB | 6.95 dB | 6.63 |

RR provides stronger reference-date separation. Across dates, RR water-sample medians are also more stable than RL, whose lake response changes substantially on several acquisitions.

### Multi-date area results

The same asset-specific thresholds and connectivity rule were applied without per-date retuning:

| Date | Platform | RR area (ha) | RR difference from median | RL area (ha) |
| --- | --- | ---: | ---: | ---: |
| 2025-07-14 | RCM3 | 74.84 | +5.77% | 82.84 |
| 2025-07-26 | RCM3 | 70.44 | -0.45% | 79.36 |
| 2025-09-12 | RCM3 | 71.08 | +0.45% | 70.28 |
| 2025-10-14 | RCM2 | 70.12 | -0.90% | 81.92 |
| 2025-10-26 | RCM2 | 70.28 | -0.68% | 80.64 |
| 2025-11-07 | RCM2 | 74.80 | +5.71% | 75.28 |
| 2026-07-05 | RCM2 | 74.92 | +5.88% | 81.88 |
| 2026-08-02 | RCM3 | 70.24 | -0.74% | 82.64 |

RR summary: median 70.76 ha, mean 72.09 ha, sample standard deviation 2.31 ha, coefficient of variation 3.20%, and range 70.12–74.92 ha. The full range is 6.78% of the median. The largest apparent deviation is +4.16 ha (+5.88%) on 2026-07-05.

RL summary: median 81.26 ha, standard deviation 4.42 ha, coefficient of variation 5.57%, and range 70.28–82.84 ha. The largest deviation is -10.98 ha (-13.51%) on 2025-09-12.

## Provisional method

### Threshold derivation

For each asset, the reference-date threshold is the midpoint between the water sample upper quartile and land sample lower quartile:

`threshold = (water Q3 + land Q1) / 2`

This produces:

- RR: water candidate when backscatter is below `-17.31 dB`;
- RL: water candidate when backscatter is below `-11.69 dB`.

The threshold is evidence-based but provisional. It has not been validated against an independent shoreline.

### Connectivity rule

Within the fixed analysis rectangle, only 8-connected thresholded components intersecting the fixed interior-water sample are retained. This removes unrelated dark land patches but makes the result dependent on the seed and on pixel connectivity.

### Selected working asset

RR is the Phase 3 working asset because it has stronger sample separation and lower multi-date variability than RL. RL remains useful as a diagnostic comparison but is not selected for the baseline area series.

## Sensitivity

Changing the RR threshold by ±1 dB changes the eight-date median area as follows:

| RR threshold | Median area |
| --- | ---: |
| -18.31 dB | 68.32 ha |
| -17.31 dB | 70.76 ha |
| -16.31 dB | 76.68 ha |

The approximately 8.36 ha span shows that absolute area is materially threshold-sensitive. The threshold must not be tuned merely to minimize temporal variation.

## Interpretation

At this stable-lake control site, the provisional RR method reports a 3.20% coefficient of variation and a largest deviation of 5.88% from the median. This is reasonably consistent for proceeding to preprocessing/alignment work, but apparent differences of this scale cannot yet be interpreted as true water-area change.

## Limitations and unresolved questions

- The dates span summer through late fall. Wind, rainfall, vegetation, shoreline mixing, and possible early cold-season effects can change radar response without changing the lake boundary.
- 2025-09-12 is the largest RL low outlier. The 2025-11-07 RR estimate is the largest RR deviation and its RL water distribution is unusually broad. These dates are flagged, not removed.
- Both RCM2 and RCM3 are present. Similar geometry does not by itself prove cross-platform radiometric equivalence.
- No additional speckle filtering, terrain correction, cross-date normalization, or independent quality-mask workflow was applied beyond the supplied CEOS-ARD processing.
- The 20 m pixels mix water and land along the shoreline.
- The result depends on the fixed analysis rectangle, samples, threshold, and seeded-connectivity rule.
- Visual inspection is insufficient for final validation. A later phase must compare the derived mask with an authoritative lake polygon or contemporaneous cloud-free Sentinel-2 water delineation.

## Phase 3 preprocessing and alignment

### RCM grid registration

All eight retained RCM windows have the following tested grid:

| Property | Result |
| --- | --- |
| CRS | EPSG:32620 |
| Pixel size | 20 m × 20 m |
| Window shape | 110 rows × 50 columns |
| Affine origin | 457000 m E, 5044100 m N |
| Bounds | 457000–458000 m E, 5041900–5044100 m N |
| Maximum cross-date origin/extent offset | 0 m / 0 pixels |

No RCM reprojection or backscatter resampling is needed inside the tested AOI. The supplied grid is preserved.

### Quality masks and support layers

Product XML defines the CEOS-ARD data-mask values as `1 = valid`, `2 = invalid`, `5 = layover`, `7 = shadow`, and `9 = layover + shadow`. RR is readable in all 5,500 AOI pixels on each date. The data mask flags 0–16 layover pixels per acquisition; only code 1 is analysis-valid. No invalid, shadow, or combined layover-shadow values occur in this window.

Mean local incidence angle is 27.97080°–27.98475° across dates, a span of only 0.01396°. The mean gamma-to-sigma ratio is 0.878532–0.878701. These stable summaries reduce concern about cross-date geometry drift, although the broad within-scene local-incidence range still matters per pixel.

### Radiometric and platform consistency

The fixed RR water/land samples remain separated on all dates, with a median gap of 10.77–13.95 dB. Four RCM2 and four RCM3 dates are present. Descriptively, their means differ as follows:

- RCM2 water-sample median is 0.71 dB lower than RCM3;
- RCM2 land-sample median is 0.93 dB higher than RCM3;
- RCM2 provisional lake area is 0.88 ha higher than RCM3 on average;
- sample local-incidence means are nearly identical.

The small sample and platform/date/season confounding do not support attributing these differences to satellite calibration. Platform identity must remain available as a diagnostic variable.

## Independent validation

### Reference sources

Two sources are used independently of the SAR-derived training samples:

1. **Sentinel-2 Collection 1 Level-2A** item `S2B_T20TMR_20250726T151759_L2A`, acquired 2025-07-26 15:20:18 UTC. It is paired with the RCM acquisition at 10:32:24 UTC, an absolute offset of 4.80 hours. Scene cloud cover is 0.005936%, and the tested AOI contains no SCL-excluded cloud pixels.
2. **Nova Scotia Hydrographic Network Wet Features** object 2385, HID `A938C361055748859F18C4E5B3FF36AE`. Its reprojected full-polygon area is 83.69 ha. It is treated as authoritative nominal hydrography, not acquisition-date shoreline truth.

### Sentinel-2 method

Earth Search B03 green and B08 NIR assets are read at their native 10 m resolution. Surface reflectance is calculated with the asset scale and offset (`DN × 0.0001 − 0.1`). The independent optical class is `NDWI = (green − NIR) / (green + NIR) > 0`, without fitting to RCM.

SCL classes 0, 1, 3, 8, 9, 10, and 11 are invalid. SCL is moved from 20 m to the 10 m spectral grid with nearest-neighbour resampling. The three-state water/non-water/unknown result is aggregated to the exact 20 m RCM grid with mode resampling. Categorical classes are not interpolated. The NSHN vector is rasterized directly on that grid with center-pixel semantics.

### Agreement results

RCM is treated as the prediction to make precision and recall direction explicit:

| Comparison | Precision | Recall | F1 | IoU | RCM / prediction area | Reference area | Area error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| RCM RR vs same-day Sentinel-2 NDWI | 0.864 | 0.906 | 0.885 | 0.794 | 70.44 ha | 67.16 ha | +3.28 ha (+4.88%) |
| RCM RR vs NSHN nominal polygon | 0.999 | 0.854 | 0.921 | 0.853 | 70.44 ha | 82.40 ha inside the fixed AOI | -11.96 ha (-14.51%) |
| Sentinel-2 NDWI vs NSHN nominal polygon | 0.957 | 0.780 | 0.860 | 0.754 | 67.16 ha | 82.40 ha inside the fixed AOI | -15.24 ha (-18.50%) |

For the primary RCM/Sentinel comparison, TP = 1,522, FP = 239, FN = 157, and TN = 3,573 across 5,491 mutually valid 20 m cells. RCM-only water is concentrated along the western/northwestern lobe and parts of the shoreline. Fewer Sentinel-only pixels occur around southern and narrow shore edges plus small disconnected patches. Mixed pixels, 10-to-20 m aggregation, optical response to vegetation/dark water, SAR roughness/speckle, and fixed thresholds are plausible contributors.

## Phase 3 conclusion and Phase 4 guardrails

The RCM series is technically suitable to continue as a **conditional relative-change baseline**: grids are exactly aligned in the tested AOI, supplied quality masking is available, geometry-support layers are stable, and the same-day independent EO comparison shows coherent lake-interior agreement.

It is not reliable enough for small absolute-shoreline claims. Phase 4 must preserve the native common grid, exclude all data-mask codes other than 1, retain the fixed RR rule, track platform, and flag only changes clearly larger than the Phase 2 stability/sensitivity envelope. Additional cloud-free optical dates are needed before interpreting a temporal signal. Folly Lake remains a control/calibration site, and no climate or causal claim is supported.

## Phase 4 real-event change-detection method

### Event feasibility and selection

Candidate cases were screened in order of scientific and access feasibility rather than visual drama:

1. The 21–23 July 2023 Nova Scotia flood was tested first. The official event was suitable, but no public `rcm-ard` or `RCMImageProducts` record intersected the tested Halifax, Hants, Lunenburg, and Queens impact AOIs in the June–August screening window. The case was rejected rather than forced.
2. The May 2025 Central Ottawa River freshet had same-platform/orbit RCM observations and official NRCan flood polygons. It was rejected because no tested grid cell rose above the 5.88 percentage-point control-site context and RCM gain had zero overlap with the official flood class in the strict common area.
3. The December 2025 Fraser Valley / Lower Fraser flood was selected. It provides seven openly downloadable NRCan Emergency Geomatics Service RCM-derived flood products, public CEOS-ARD observations bracketing the event, independent Sentinel-2 coverage, official flood/impact reporting, and an infrastructure layer.

The fixed 6 km × 6 km Chilliwack-area AOI is EPSG:32610 bounds `(563960, 5443240, 569960, 5449240)`, approximately WGS84 `(-122.123101, 49.138657, -122.039809, 49.191968)`. It was chosen from the strict intersection of all seven EGS footprints and the two public ARD mosaics. The AOI is a compact evidence-chain study area, not a claim about the location of maximum event impact.

### Event imagery preprocessing

The main event sequence uses NRCan EGS categorical vectors acquired from 12 to 21 December 2025. Flood, permanent-water, and footprint shapefiles are clipped to the AOI, reprojected to EPSG:32610, and rasterized on a fixed 20 m grid using pixel-centre semantics. Class 1 represents permanent water and class 2 represents open-water flood. Footprints define valid pixels. The seven inputs have Moderate product confidence and mixed 5, 16, and 30 m source resolutions, which remain explicit metadata.

Two public CEOS-ARD mosaics provide real pre/post RCM observations: 8 November 2025 and 7 January 2026, both RCM3 relative orbit 166 ascending. Only `data_mask == 1` is valid. RR, local-incidence angle, and gamma/sigma ratio are continuous and are bilinearly reprojected to the fixed 20 m grid; the categorical data mask uses nearest-neighbour. The Phase 3 rule `RR < -17.314 dB` plus seeded 8-connectivity is applied only to this matching CEOS-ARD representation. It is not transferred to EGS classes or Level-1 imagery.

Sentinel-2 B03/B08 reflectance uses STAC scale/offset and native 10 m NDWI. SCL classes 0, 1, 3, 8, 9, 10, and 11 are invalid. SCL is moved to 10 m with nearest-neighbour, and the water/non-water/unknown class is aggregated to 20 m with mode. The 2 December image is the optical pre-event support; the 27 December image is the recovery-period comparison. Cloud-obstructed event-window scenes are not forced into the analysis.

### Change and grid logic

The comparable EGS semantic masks are:

- pre-event semantic baseline: permanent water from the first EGS product;
- near-event water: permanent water plus 12 December open-water flood;
- recovery water: permanent water plus 21 December open-water flood.

The semantic baseline is not mislabelled as a dated RCM acquisition; the actual 8 November ARD observation is displayed separately. Pixel changes are classified as persistent non-water, persistent water, water gain, water loss, or invalid/unknown. Water gain is the primary event signal.

A fixed 1 km grid provides a local denominator of up to 2,500 20 m cells. Each cell records valid count/percentage, baseline, near-event and recovery water ratios, percentage-point differences, changed area, benchmark status, and temporal class. The grid size was selected for local interpretability and shoreline-noise suppression, not to maximize apparent change.

### Normal versus anomaly

Three distinct concepts govern Phase 4 interpretation:

1. **Method/sensor benchmark.** Folly Lake is a relatively stable control site. Its 3.20% coefficient of variation, 5.88% maximum single-date deviation, and 4.88% same-day RCM/Sentinel area difference describe variability observed in this workflow. They are contextual checks from another landscape, not formal significance levels or universal flood thresholds.
2. **Site-specific normal baseline.** A real-event baseline should preferably be estimated within the fixed event AOI from multiple seasonally and radiometrically comparable pre-event observations. For a river/floodplain, this means characterizing where water is normally present inside the AOI rather than estimating a river's total area. The already-discovered Lower Fraser data provide only one pre-event RCM-ARD acquisition and one pre-event Sentinel-2 observation. Neither is semantically interchangeable with the EGS event classes, so a defensible multi-date water-frequency baseline is not constructed. The current provisional local baseline remains the EGS permanent-water class.
3. **Event anomaly.** An anomaly is EGS flood water mapped outside that local permanent-water baseline. Interpretation combines the size of the local deviation, spatial concentration and continuity, recession or persistence, independent EO/official-source agreement, and impact context. No single percentage decides whether a flood is significant.

The 1 km table therefore labels the binary EGS baseline without arbitrary probability cutoffs: a cell is normally dry only when its baseline ratio is 0%, permanent-water only when it is 100%, and otherwise mixed. Its anomaly field states whether mapped gain is absent, lies within the Folly Lake control context, or is above that context while still requiring corroboration. Temporal classification is based on the observed event-to-recovery trajectory, not on crossing 5.88%.

### Uncertainty, temporal behaviour, and validation

The Folly Lake CV 3.20%, maximum single-date deviation 5.88%, and same-day RCM/Sentinel area difference 4.88% remain empirical feasibility context rather than formal confidence limits. The event AOI gained 54.92 ha from the EGS semantic baseline, about 13.2 times the approximately 4.16 ha absolute maximum deviation implied at the 70.76 ha control median. The AOI-wide relative increase is 5.65%, close to the 5.88% control value, while two local grid cells are above 5.88 percentage points (maximum 21.50 points). Those two cells are stronger candidates for attention, not automatically significant detections. Interpretation emphasizes spatial coherence, local magnitude, the official timeline, temporal evolution, and multi-source evidence rather than a single cutoff.

Open-water flood area declined from 54.92 ha on 12 December to 21.64 ha on 21 December. The event is classified as **recovering with localized residual/persistent expansion**. It is not treated as a long-term environmental trend.

The recovery-period RCM water mask (21 December) is compared with Sentinel-2 NDWI (27 December) on mutually valid cells. RCM is the prediction for metric direction. Precision is 0.663, recall 0.978, F1 0.790, and IoU 0.653. The 6.2-day timing offset, recession, cloud/SCL exclusions, resolution, mixed shoreline cells, vegetation, and different SAR/optical physics are plausible disagreement causes.

OpenStreetMap road ways are intersected with the near-event water-gain geometry. Fourteen ways intersect over 0.346 km, including one bridge-tagged way. These are described only as **intersecting** or **potentially exposed**; satellite overlap is not proof of physical damage, closure, depth, or traffic impact.
