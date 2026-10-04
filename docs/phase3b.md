# Phase 3B — final implementation and closure

2026-10-04. **FINAL EXPERIMENTAL FAIL — RESEARCH FROZEN.**
This is the authoritative 3B status. Earlier Simple/Lee/Multisource/RF v1
gate files remain historical evidence, not invitations to rerun or refine.
No further Phase3B v3/v4 or tuning round follows this task.

## A. Files and namespaces

- Final policy: `analysis/rf_final.py`; original RF model/features remain in
  `analysis/rf_classification.py`.
- Original EGS reference contract: `analysis/phase3b_references.py`.
- Corrected coverage: `analysis/rcm_preprocessing.py`.
- Restored registered mode-group gate: `analysis/validation.py`.
- One-time runner/report: `scripts/phase3b_final.py`; refuses overwriting a
  completed result. `phase3b_fresh_inputs.py` fetches only minimal FWA windows.
- Read-only smoke checker: `scripts/phase3b_check_final.py`; direct tests:
  `scripts/phase3b_tests.py`, `tests/test_phase3b_final.py`.
- Saved-mask contribution/figure audit: `scripts/phase3b_final_audit.py`,
  no retraining or parameter selection.
- Results: `data/processed/phase3b/rf_v2_final/`; dedicated original-vector
  snapshots: `data/processed/phase3b/references/`.
- Final notebook, README, research record and decision/project-plan entries.
  No existing Simple/Lee/multisource/RF v1 result was deleted or moved.

## B. Final method

`phase3b_rf_v2_final`: scene-specific RF, 200 trees, depth12, leaf5,
balanced_subsample, seed20261004; same 20×20-block balanced sampling.
ECCC 1984–2023 frequency0 is stable land, >=80 stable water; 1–79/nodata
excluded. Four unchanged features: Sigma0HH dB, Sigma0HV dB, HH−HV dB,
3×3 final-grid HH standard deviation. EGS never supplies RF training labels.

Water score>=0.50; subtract the fixed initial-product EGS semantic class1;
retain elevation<=5m OR score>=0.90 within60m of independent FWA.
8-connectivity/min4; retain1–3 pixels ONLY if mean score>=0.90 and ALL
component pixels are within60m. No date-specific thresholds, feature additions,
smoothing, dilation, erosion or new hole filling. Proximity is not hydraulic
connectivity. Copernicus is DSM, not bare-earth DTM.

Distance retains the existing 30m rasterized/all-touched FWA Euclidean proximity
convention, not exact vector distance; rasterization and AOI-edge context are
limitations. Reason codes are overlapping bit flags:
1 normal terrain;2 terrain exception;4 terrain rejected;8 normal component;
16 retained small component;32 cleanup removed;64 semantic subtraction.
Nodata255 is distinct from a valid zero-reason pixel.

## C. Coverage QA fix

Uncovered source zeros now enter the averaging denominator rather than being
excluded as nodata. An explicit validity mask permits finite zero power as
covered; dB-ready final power must still be positive. Synthetic0/.5/.95/1 cases
pass. Native caches were reaggregated, without overwriting old caches.
Every pilot has40,000 valid cells/100%; all RF probability arrays match v1
exactly. This bug did NOT explain five-scene RF performance.

## D–E. Primary and legacy reference contracts

PRIMARY: raw original EGS class2 vector, one reprojection toEPSG:32610,
one center rasterization to30m; original footprint defines EGS valid coverage.
Compact source snapshots retain product identity/UTC/class meaning/source
sidecar hashes/CRS/grid hash/rasterization, plus source ZIP URL.

LEGACY: Phase4 20m center raster → vectorization →30m center raster.
It remains a comparison, not source of truth for final validation.
RF v1 is evaluated on BOTH references for like-for-like comparison.
No raw-v2 versus legacy-v1 improvement claim is made.
The existing fixed class1 semantic subtraction was not replaced by a
per-date reference; conflicts with original class2 remain a limitation.

## F. Five-scene final metrics

All dates UTC, December2025; five valid domains each36km².
Full TP/FP/FN/TN, area/bias, boundary30/60m and component metrics are in
`final_validation_metrics_raw_egs.csv` and `final_validation_metrics_legacy.csv`.

| Date | Precision | Recall | F1 | PRIMARY IoU | LEGACY IoU | Predicted / primary-reference ha | Primary bias % |
|---|---:|---:|---:|---:|---:|---:|---:|
| 14 | .424 | .553 | .480 | .316 | .364 | 26.73 / 20.52 | +30.26 |
| 15 | .699 | .416 | .522 | .353 | .409 | 30.24 / 50.85 | −40.53 |
| 17 | .635 | .486 | .551 | .380 | .426 | 28.08 / 36.63 | −23.34 |
| 19 | .464 | .462 | .463 | .301 | .335 | 29.07 / 29.25 | −0.62 |
| 21 | .568 | .621 | .593 | .422 | .497 | 23.13 / 21.15 | +9.36 |

Primary macro: medianIoU.352853, medianF1.521643, worstIoU.301205,
medianP.568093/R.486486, medianabsbias23.3415%; pooledIoU.351852.
Primary TP855/FP670/FN905/TN197570; FP60.30ha/FN81.45ha.
Legacy medianIoU.409091/F1.580645, worstIoU.334711,
medianabsbias24.6377%, pooledIoU.402319; FP52.92ha/FN72.36ha.

## G. Fresh spatial holdout

Fixed bounds(570110,5444740,571430,5447740), 30m,44×100.
Policy and AOI fixed before fresh performance. Same per-scene RF trained on
MAIN AOI historical labels; no fresh-AOI training and no performance retuning.
Only three minimal official FWA snapshots were fetched, with URL/date/hash.
No new satellite products or national rasters were downloaded.

| Date | Valid % | Precision | Recall | F1 | IoU | Predicted / reference ha | Bias % |
|---|---:|---:|---:|---:|---:|---:|---:|
| 15 | 99.864 | .956 | .500 | .656 | .489 | 4.05 / 7.74 | −47.67 |
| 19 | 99.841 | .830 | .609 | .703 | .542 | 4.23 / 5.76 | −26.56 |

This is a fresh neighboring spatial check, not cross-event or independent-sensor
validation. It cannot replace or rescue the main five-date gate.

## H–I. Progression and representation comparison

| Method | LEGACY median IoU / F1 | PRIMARY median IoU / F1 |
|---|---:|---:|
| Simple SAR | .109 / .196 | not newly evaluated |
| Lee SAR | .140 / .246 | not newly evaluated |
| Multisource v1 | .283 / .441 | not newly evaluated |
| RF v1 | .333 / .500 | .296 / .457 |
| RF v2 final | .409 / .581 | .353 / .522 |

The entire final gain is modest; representation changes cannot make it pass.
Repeated research on the same five dates limits independent generalization.
Do not compare scores across different references as algorithmic improvement.

## J–K. Terrain and cleanup contributions

Relative to fixed normal-terrain/min4 RF v1:
- Terrain exception with ordinary cleanup: net87 added pixels,61TP/26FP
  under BOTH references, no removed pixels.
- Confidence-aware small components:138 additional pixels; PRIMARY51TP/87FP,
  LEGACY65TP/73FP.
- Total final additions:225 pixels; PRIMARY112TP/113FP, LEGACY126TP/99FP.

These net contributions differ from counting every exception pixel before
cleanup. The raw terrain-exception reason contains162 pixels (84TP/78FP
on primary reference); not all survive cleanup. Detailed per-date reason and
net-change tables prevent double counting. The small-component rule does not
guarantee increased precision.

## L–M. Per-mode results and final gate

Primary medianIoU: stripmap16_desc.380038 (3 scenes), scansar30_asc.327029
(2 scenes). Legacy:.426326/.371901.

Original GO thresholds unchanged: medianIoU>=.50/F1>=.67; every scene
IoU>=.35/F1>=.52; each mode medianIoU>=.45; medianabsbias<=25% and each<=50%;
calibration, geometry, systematic artifact QA and full provenance.
Accuracy and both mode-group thresholds fail. Calibration sampled LUT/grid
checks pass; independent static shoreline QA is not absolute geolocation
certification, and systematic-artifact absence is not certified.
Missing QA never silently passes. Final state has no REFINE option.

## N–O. Stop and promotion status

**FINAL EXPERIMENTAL FAIL.** `final_gate_status.json` is authoritative.
No `method_config_v1.json`; no remaining-six processing; no Phase4B promotion.
Policy is frozen as a FAILED experimental method definition, not an accepted
operational configuration. Existing EGS production workflow is unchanged.

## P–Q. Documentation and notebook

README now separates Research & Method Selection from Translation & Impact
Communication. It explains accessible16m/30m Level-1 versus unmatched5m EGS
acquisitions without claiming a proven causal accuracy advantage.
`docs/phase3b_method_research.md` permanently consolidates the threshold,
multisource, RF, rejected directions, geometry/reference/mixed-pixel findings
and final stop. The notebook presents20 final narrative sections followed by
preserved historical failures, tables and images; it reads saved artifacts only.
The RF v1 relative-path issue is fixed for root or notebooks-directory launch.

## R. Data and Git hygiene

No valuable evidence was deleted. Root Simple/Lee paths are retained for
compatibility; multisource,rf_v1,rf_v2_final,references andqa are clearly labelled.
No uncontrolled scratch references are added.

| Artifact | Role | Git policy |
|---|---|---|
| data/raw/rcm_level1 | vendor/licensed source imagery | local-only, ignored |
| phase3b/cache and native SNAP/DEM | heavy reproducible intermediates/input caches | local-only, ignored |
| historical AOI raster and existing FWA/landuse snippets | independent small source snapshots + provenance | existing trackable evidence retained |
| final CSV/JSON, masks/reasons/disagreement, compact QA | derived reproducibility evidence | trackable |
| final original EGS vector snippets and fresh FWA | small versioned source snapshots + hash/URL | trackable |
| final float probabilities | regenerable inference cache | local-only, ignored; hashes recorded |
| notebook checkpoints, OS files, scratch, logs | temporary | ignored |
| /tmp research | prior temporary research | no project runtime/history dependency |

The full local smoke checker intentionally needs local protected caches and
probability files; a fresh clone can view summary/metrics without those caches.
Heavy upstream snapshots are not downloaded during Notebook/Dashboard startup.

## S. Tests and verification

Pytest is unavailable; no package was installed. All 27 direct tests passed,
and all 42 notebook code cells executed from both repository-root and notebook
working directories. Notebook schema and 94 unique cell IDs also passed.
Direct assertions are executed
using temporary fixtures, including historical labels, reproducible/balanced RF,
feature order, EGS exclusion, .90/60m boundaries, component means/ALL-pixel rules,
semantic subtraction, original-vs-legacy contract, coverage0/.5/.95/1,
CRS/transform/shape, mode gate, fresh non-retuning, frozen overwrite refusal.
`phase3b_check_final.py` verifies manifest, protected inputs, unchanged scores
and area identities. Python compile, notebook JSON/code-cell checks, complete
read-only Notebook code execution, and `git diff --check` are part of closure.
No full SNAP rerun, pytest run, or new five-scene parameter search is claimed.

## T. Git status and protected scope

No commit created. Changed/new files are confined to Phase3B code,tests,Notebook,
documents,ignore policy and final/reference evidence. Content hashes confirm
256 protected files unchanged, including app.py,Phase4/5 notebooks/outputs,
old RF v1/multisource, masks and caches. Exact changed paths are available in
`git status --short`; reproducible reports are not automatically staged.

## U. Scientific conclusion and viewing

Phase 3B final experimental Level-1 method did not meet the pre-registered
operational GO gate. The method is retained as validated research evidence, while
the existing EGS workflow remains the production source for the prototype.

```bash
conda activate space-hackathon-2026
python scripts/phase3b_final.py        # saved summary, no training or network
python scripts/phase3b_tests.py        # direct tests, no pytest required
python scripts/phase3b_check_final.py  # full local artifact verification
jupyter lab                          # open 03b_level1_validation.ipynb
```

Only the3B notebook needs Run All to display the finalized saved evidence.
Phase1–5/Dashboard need no rerun. No further Phase3B research iteration is
recommended. This task closes Phase3B.
