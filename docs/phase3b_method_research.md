# Phase 3B method research — final, closed

2026-10-04. Phase 3B research and implementation are frozen. This record
consolidates the important conclusions formerly held in temporary research
directories; those directories are no longer required to understand the method.
No RF v3/v4, further feature search, or threshold-chasing round is authorized.

## Scientific progression

1. Eleven local RCM Level-1 GRD products were inventoried/checksummed. Only five
   matched EGS acquisitions (14/15/17/19/21 Dec 2025) were processed for validation.
   SNAP 14 read, calibrated, and Range-Doppler terrain-corrected HH/HV. The fixed
   scientific grid is EPSG:32610, 30 m, 200×200, 36 km².
2. Implementation diagnosis corrected the Otsu histogram-count factor and
   Gamma-first versus Sigma-first band ordering. Vendor LUT checks at six native
   samples across 16M9 and SC30MB found Sigma0 relative errors below 3e-8.
   This checks sampled calibration, not every pixel. Gamma diagnostics are not
   substituted for the frozen Sigma0 model.
3. Simple SAR median legacy IoU/F1 was 0.109/0.196. The registered Lee comparison
   reached 0.140/0.246. Dark lowland surfaces and shoreline omissions prevented GO.
4. Independent Copernicus DSM, AAFC land use, and BC FWA context reduced extensive
   false positives. Multisource v1 reached 0.283/0.441, but median absolute area
   bias remained 68.2%. A DSM is not a bare-earth DTM or a water-level model.
5. Public NRCan methodology motivated scene-specific RF, historical training
   labels, dual-polarization inputs and a distinction between classified pixels
   and an operational mapping product. ECCC 1984–2023 frequency 0 supplied land,
   >=80 water, 1–79 and nodata excluded. EGS was never an RF training label.
6. RF v1 used Sigma0 HH/HV, HH−HV and final-grid 3×3 HH standard deviation,
   balanced 20×20-block sampling, 200 trees/depth12/leaf5 and fixed seed 20261004.
   Legacy median IoU/F1 became 0.333/0.500, bias 19.7%; still FAIL.

## Rejected directions and error diagnosis

Probability-threshold search lacked robust cross-date gains; probability
calibration was unstable. Incidence angle, Gamma0 replacement, native texture,
simplified HAND, stricter historical-water labels/stable-land resampling and
bright-return flooded-vegetation reasoning did not justify further model
expansion. No independent flooded-vegetation truth was available. These were
bounded exploratory studies, not independent validation or operational features.

Terrain and cleanup removed some high-score true positives. Broad relaxation
also admitted false positives; neither global two-pixel cleanup nor dilation,
erosion or hydraulic-connectivity claims was justified. The final narrow policy
uses proximity to independently sourced FWA, not EGS overlap.

About 94.62% of RF v1 false negatives fell within 30 m of the reference boundary,
but 94.72% of reference positives themselves were in that band. This does NOT
prove 95% of errors are geometric misregistration. About 50% of false negatives
were in original EGS pixels with >75% polygon coverage; mixed pixels cannot
explain all remaining errors. False-positive area far from reference also remained.

Independent static FWA shoreline/radiometric-transition QA gave median absolute
offsets 9/21/9/24/9 m, P95 52.5/60/54/51/51 m. ScanSAR dates were similar; no
15-Dec-specific severe warp was established. Historical shorelines and SAR
radiometric edges are not absolute contemporaneous geolocation truth. No image
shift was applied; absolute geometry and systematic-artifact certification remain
unresolved, and are not silently treated as passing gates.

## Reference and coverage findings

Legacy EGS validation had undergone original vector → 20 m center sampling →
vectorization → 30 m center sampling. Thin geometries changed even when areas
were similar. Final primary validation instead reprojects the original EGS class-2
vector once and center-rasterizes once at 30 m, including the product footprint.
RF v1 was recomputed on that same primary reference (median IoU 0.296), so its
legacy 0.333 is not directly compared with RF v2's raw-reference score.
Original source hashes, product identity/UTC, class meaning, CRS and grid hashes
are retained with compact dedicated snapshots.

The fixed initial-product EGS class-1 subtraction remains a semantic reference,
not observed pre-event normal water. It still uses the existing exported semantic
geometry; some primary raw class-2 pixels conflict with this derived reference.
That is a documented limitation, not permission for per-date reference changes.
Historical frequency is a training prior, a separate role from semantic subtraction.

Coverage averaging had incorrectly treated uncovered zeros as nodata and excluded
them from the denominator. The fix includes those zeros, retains explicit-source
valid zero-power coverage, and keeps positive-power requirements for dB-ready
cells. Synthetic 0/50/95/100% tests pass; all five native TC caches reaggregate to
40,000 valid cells and exactly unchanged RF scores. This bug did not cause their
classification performance.

## Final RF v2 and outcome

The RF/features/training/seed are unchanged. Water score >=0.5; semantic class-1
subtraction; elevation <=5m or score >=0.90 within 60m of FWA; 8-connectivity,
minimum4; 1–3-pixel components retained only if mean score>=0.90 and ALL component
pixels are within60m. No hole filling or smoothing is added. Reasons are recorded
as overlapping uint8 bits. Policy, reference and neighboring AOI were fixed before
final results; no final-result retuning occurred.

Five-date primary median IoU/F1: **0.353/0.522**, worst IoU **0.301**; median
absolute bias **23.34%**, pooled IoU **0.352**. Stripmap median IoU **0.380**;
ScanSAR **0.327**. Legacy median IoU/F1 **0.409/0.581**, worst **0.335**. Primary
FP/FN totals are60.30/81.45ha versus legacy52.92/72.36ha. Area bias alone does
not establish correct spatial detection.

The fixed neighboring AOI is (570110,5444740,571430,5447740), 44×100 at30m.
Main-AOI historical-label RF models were applied without fresh-AOI training.
15/19-Dec coverage is99.864/99.841%; IoU0.489/0.542, F10.656/0.703, bias
−47.67/−26.56%. This is a fresh spatial check in the same event, not cross-event
generalization or independent-sensor truth. It did not trigger tuning and cannot
replace the five-date gate. Three minimal official FWA windows and hashes are saved.

The same five dates have informed repeated prior research; final fixed-policy
results are not a new blind cross-event validation. Concurrent Sentinel-2 is mostly
cloudy (15-Dec0%, 19-Dec0.047%, 17-Dec11.82% clear chiefly water), so it cannot
provide representative event-time flood/land validation. Later recovery imagery
does not certify an earlier acquisition. Only16m and30m Level-1 products were
locally accessible; operational EGS includes some5m acquisitions not in this local
set. Finer acquisition, ancillary context, filtering, independent product
processing and manual QC are plausible contributors, not quantified causes.

## Final stop

**FINAL EXPERIMENTAL FAIL.** Median accuracy, weakest-date accuracy and both
mode-group gates fail; absolute geometry/systematic-artifact checks are not
certified. The original thresholds remain unchanged. No method_config_v1.json,
remaining-six-scene processing, Sentinel holdout promotion or Phase4B handoff.
No further Phase3B research iteration is planned or recommended.

Phase 3B final experimental Level-1 method did not meet the pre-registered
operational GO gate. The method is retained as validated research evidence, while
the existing EGS workflow remains the production source for the prototype.

## Primary documentation

- [NRCan EGS product record](https://open.canada.ca/data/en/dataset/9cad712a-5ac5-4248-b7d7-2db1a3892509)
- EGS Flood Extent Product Guide (2023-02-07), included in original EGS ZIPs:
  scene-dependent classification, filtering/vectorization, ancillary checks and
  manual QC; no exact public universal RF/cleanup configuration is asserted.
- [NRCan Open File 8434](https://publications.gc.ca/site/eng/9.853128/publication.html)
- [BC FWA user guide](https://www2.gov.bc.ca/assets/gov/data/geographic/topography/fwa/fwa_user_guide.pdf)
- [Copernicus DEM license/description](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM/resources/license/License-COPDEM-30.pdf)

Machine-readable final evidence is in `data/processed/phase3b/rf_v2_final/`;
`final_run_manifest.json` records output/code hashes and `final_gate_status.json`
is the authoritative Phase3B closure status. Earlier gate files are historical.
