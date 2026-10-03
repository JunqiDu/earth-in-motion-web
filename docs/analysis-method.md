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
