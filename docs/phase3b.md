# Phase 3B — RCM Level-1 pilot

Phase 3B is isolated from the existing EGS-based Phase 4/5 outputs and
Dashboard. It establishes a reproducible input inventory and the interfaces
needed for a five-scene RCM Level-1 pilot.

## Preflight

From the repository root, run:

```bash
conda activate space-hackathon-2026
python scripts/phase3b_preflight.py
```

This writes the metadata-only inventory, common-grid contract, checksum status,
candidate definitions, and pending validation manifest under
`data/processed/phase3b/`. It never opens the large TIFFs and never queries a
remote service. The verified ESA SNAP 14 executable on this Mac is
`/Applications/esa-snap/bin/gpt`. Set it for the current shell with
`export SNAP_GPT=/Applications/esa-snap/bin/gpt`; the preflight does not modify
`~/.zshrc`.

## Fixed grid and pilot

The grid is EPSG:32610, bounds `(563960, 5443240, 569960, 5449240)`, 30 m,
200×200, and 0.09 ha per pixel. The registered pilot is the five RCM/EGS
overlap acquisitions on 14, 15, 17, 19, and 21 December 2025. No method is
frozen and no Phase 4/5 artifact is replaced before the GO gate is met.

The Pilot uses `config/snap/phase3b_calibration.xml` followed by
`config/snap/phase3b_terrain_correction.xml`.  The terrain graph explicitly
orders `Gamma0_HH`, `Gamma0_HV`, `Sigma0_HH`, and `Sigma0_HV`; SNAP 14 leaves
the GeoTIFF descriptions blank, so the pipeline uses that declared graph order
rather than the source DIMAP's Sigma-first order.  It fails explicitly when
GPT is unavailable and does not substitute a GCP-only warp.

## Checks

The Python smoke checks can be run with:

```bash
python -m py_compile analysis/*.py scripts/*.py
python -m pytest -q tests/test_phase3b.py  # if pytest is installed
git diff --check
```

`method_config_v1.json` is intentionally absent until a real SNAP pilot has
passed the registered geometry, calibration, LOODO, accuracy, and area-bias
gates.

## Two-scene smoke test

After preflight passes, run only the registered P01/P02 smoke test:

```bash
python scripts/phase3b_smoke_test.py --gpt "$SNAP_GPT"
```

It uses SNAP Calibration and Range-Doppler Terrain-Correction, then aggregates
Gamma0 linear power to the fixed 30 m grid. Outputs are written below the
ignored `data/processed/phase3b/cache/smoke/` directory.

## Formal five-scene Pilot status

The formal Pilot is run only after the smoke test:

```bash
python scripts/phase3b_pipeline.py dem-provenance
python scripts/phase3b_pipeline.py preprocess-pilot
python scripts/phase3b_pipeline.py validate-pilot
python scripts/phase3b_diagnostics.py summarize
python scripts/phase3b_diagnostics.py lut-qa
python scripts/phase3b_pipeline.py preprocess-refinement-lee
python scripts/phase3b_pipeline.py validate-refinement-lee
python scripts/phase3b_pipeline.py finalize-pilot
```

On the current Mac, SNAP 14.0.0 completed calibration, Range-Doppler terrain
correction, and 30 m aggregation for all five registered scenes. The outputs
are EPSG:32610, 40,000 valid grid cells per scene, and preserve Sigma0 and
Gamma0 HH/HV arrays in the ignored pilot cache.

The preflight operator check confirms `Calibration`, `Terrain-Correction`, and
the `RCM` input format are registered in GPT.

## Completed audit and final Pilot gate

The Pilot audit found and corrected two implementation defects before the
scientific gate was evaluated:

1. The Otsu between-class variance omitted a histogram-count factor. It could
   select a sparse bright-backscatter tail as the water/land split, making the
   `HH < threshold` classifier mark almost all non-reference pixels as water.
2. The blank-description terrain-corrected GeoTIFF had initially been read in
   the calibrated DIMAP's Sigma-first order although the terrain graph emits
   Gamma-first order.

The five scenes subsequently passed product checksum, SNAP read, terrain
geometry, 30 m coverage, and calibration checks.  Every AOI grid has 40,000
valid pixels.  Native SNAP Sigma0 agrees with the vendor LUT calculation
`(DN² + offset) / gain` at six safe interior samples spanning 16M9 and SC30MB
with relative error below `3e-8`; Gamma0 is materialized from SNAP's documented
virtual expression and retained as a separate diagnostic.

`calibrated_value_distributions.csv`, `mask_area_audit.csv`,
`reference_rasterization_audit.json`, `calibration_lut_qa.csv`, and the two
local diagnostic images in `qa_figures/` document the numerical, mask,
reference-CRS, and visual checks.  The Phase 4 GeoJSON reference files both
declare EPSG:32610 and are rasterized with pixel-centre semantics.  The fixed
class-1 file remains a semantic permanent-water reference, not a normal-water
or pre-event hydrologic observation.

The corrected baseline evaluates all three pre-registered classifier families
across Gamma0 and Sigma0 under leave-one-date-out validation.  The simplest
candidate within 0.02 of the best median result is C0/Sigma0: median IoU
`0.109`, median F1 `0.196`, and worst-date IoU `0.027`.  These values are far
below the registered FAIL boundary.  A single permitted physical-scale Lee
comparison (5×5 at 16 m; 3×3 at 30 m, before 30 m aggregation) increased that
candidate's median IoU to `0.140`, but its worst-date IoU remained `0.024`.
It therefore cannot make the method eligible for the five-scene GO gate.

The final recorded status is **FAIL**, in
`data/processed/phase3b/phase3b_final_gate.json`.  This is an informative
scientific result: the validated SNAP processing path is sound, but the
restricted explainable open-water classifier does not generalize to the EGS
class-2 reference at the required accuracy. `method_config_v1.json` is
intentionally absent; the remaining six scenes, Sentinel-2 holdout, and
Phase 4B are not run. Existing EGS Phase 4/5 artifacts and the Dashboard are
untouched.

The first local run may need permission for SNAP to create its own
`~/.snap/var/cache/temp` files. This is an environment/cache permission issue;
it does not change the scientific processing contract.
