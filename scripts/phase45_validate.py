#!/usr/bin/env python
"""Read-only, offline Phase 4/5 integration validation; no export regeneration."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.phase45_contract import method_selection


def close(actual, expected, atol=1e-7):
    np.testing.assert_allclose(actual, expected, atol=atol, rtol=1e-9)


def validate(repo=ROOT):
    p4, p5 = repo / "data/processed/phase4", repo / "data/processed/phase5"
    audit = json.loads((p4 / "temporal_audit.json").read_text())
    handoff = json.loads((p5 / "phase6_handoff.json").read_text())
    assert audit["analysis_crs"] == handoff["crs"] == "EPSG:32610"
    assert audit["grid_resolution_m"] == 20
    bounds = audit["aoi_bounds_utm"]
    aoi = box(*bounds)
    transform = from_origin(bounds[0], bounds[3], 20, 20)
    shape = (300, 300)
    close(aoi.area / 1e6, 36)
    for name, digest in audit["source_artifact_sha256"].items():
        assert hashlib.sha256((p4 / name).read_bytes()).hexdigest() == digest, name
    tables = {}
    for directory in (p4, p5):
        for path in directory.glob("*.csv"):
            frame = pd.read_csv(path)
            assert not frame.duplicated().any(), path.name
            tables[path.name] = frame
    for kind in ("tables", "vectors"):
        assert all((p5 / name).exists() for name in handoff[kind])
    for kind in ("phase4_tables", "phase4_vectors", "phase4_metadata"):
        assert all((p4 / name).exists() for name in handoff[kind])
    provenance = json.loads((p5 / "source_provenance.json").read_text())
    for relative, digest in provenance["artifact_sha256"].items():
        assert hashlib.sha256((repo / relative).read_bytes()).hexdigest() == digest, relative
    assert all((repo / "assets/phase5" / name).exists() for name in handoff["maps"])
    obs = tables["event_observations.csv"]
    timestamps = pd.to_datetime(obs.timestamp_utc, utc=True)
    assert len(obs) == audit["observation_count"] == 7
    assert obs.observation_id.is_unique and timestamps.is_unique and timestamps.is_monotonic_increasing
    assert obs.relative_orbit.isna().all()  # unavailable, not invented
    assert obs.valid_pixels.eq(90000).all() and obs.valid_pct.eq(100).all()
    close(obs.fixed_reference_water_ha, 971.88)
    close(obs.raw_permanent_water_ha, [971.88]*3 + [973.28]*4)
    vectors = {}
    for directory in (p4, p5):
        for path in directory.glob("*.geojson"):
            frame = gpd.read_file(path)
            assert frame.crs.to_epsg() == 32610, path.name
            assert frame.geometry.is_valid.all() and not frame.geometry.is_empty.any(), path.name
            # Full nominal 1 km boundary cells intentionally extend beyond AOI.
            if path.name != "priority_grids.geojson":
                assert frame.geometry.difference(aoi.buffer(1e-7)).area.sum() < 1e-6, path.name
            vectors[path.name] = frame

    def mask(geometry):
        return rasterize([(geometry, 1)], out_shape=shape, transform=transform, all_touched=False).astype(bool)

    frames = vectors["egs_open_water_flood_frames.geojson"].set_index("observation_id")
    assert set(frames.index) == set(obs.observation_id)
    masks = {key: mask(row.geometry) for key, row in frames.iterrows()}
    reference = mask(vectors["egs_permanent_water_reference.geojson"].geometry.union_all())
    close(reference.sum() * .04, 971.88)
    for row in obs.itertuples():
        m = masks[row.observation_id]
        close(m.sum() * .04, row.egs_open_water_flood_ha)
        assert not (reference & m).any()
        close((reference | m).sum() * .04, row.fixed_reference_total_water_ha)
        close(frames.loc[row.observation_id].geometry.area / 10000, row.egs_open_water_flood_ha)
        assert pd.Timestamp(frames.loc[row.observation_id].timestamp_utc) == pd.Timestamp(row.timestamp_utc)
    initial, final = masks["OBS01"], masks["OBS07"]
    endpoint_masks = {"persistent_initial_flood": initial & final,
                      "gross_recession": initial & ~final, "recovery_only": final & ~initial}
    transition = vectors["endpoint_transition.geojson"].set_index("transition_class")
    for key, m in endpoint_masks.items():
        assert np.array_equal(mask(transition.loc[key].geometry), m)
        close(transition.loc[key].area_ha, m.sum() * .04)
    close(initial.sum()*.04, 19.48 + 35.44)
    close(final.sum()*.04, 19.48 + 2.16)
    close(35.44 - 2.16, 1026.80 - 993.52)
    for row in tables["acquisition_comparisons.csv"].itertuples():
        before, after = masks[row.from_observation], masks[row.to_observation]
        close(row.overlap_ha, (before & after).sum()*.04)
        close(row.lost_ha, (before & ~after).sum()*.04)
        close(row.new_ha, (~before & after).sum()*.04)
        close(row.net_change_ha, int(after.sum())*.04-int(before.sum())*.04)
        close(row.jaccard, (before & after).sum()/(before | after).sum())
    for row in tables["beam_family_comparisons.csv"].itertuples():
        before, after = masks[row.from_observation], masks[row.to_observation]
        close(row.from_area_ha, before.sum()*.04)
        close(row.to_area_ha, after.sum()*.04)
        close(row.net_change_ha, int(after.sum())*.04-int(before.sum())*.04)
        close(row.overlap_ha, (before & after).sum()*.04)
        close(row.jaccard, (before & after).sum()/(before | after).sum())
        assert row.net_change_ha < 0
    units = tables["event_hydrology_unit_values.csv"].copy()
    units["timestamp_utc"] = pd.to_datetime(units.timestamp_utc, utc=True)
    assert not units.duplicated(["timestamp_utc", "station_id", "parameter"]).any()
    stages = tables["hydrologic_stage_summary.csv"]
    for row in stages.itertuples():
        subset = units[(units.station_id == row.station_id) & (units.parameter == row.parameter)
                       & (units.timestamp_utc >= pd.Timestamp(row.start_utc))
                       & (units.timestamp_utc < pd.Timestamp(row.end_utc))]
        expected = subset.value.min() if row.statistic == "min" else subset.value.max()
        close(row.value, expected)
        assert ((subset.timestamp_utc == pd.Timestamp(row.anchor_timestamp_utc)) & subset.value.eq(row.value)).any()
    alignment = tables["rcm_stage_alignment.csv"]
    assert len(alignment) == 7 and alignment.observation_id.is_unique
    for row in alignment.itertuples():
        close(row.offset_to_stage_anchor_hours,
              round((pd.Timestamp(row.timestamp_utc)-pd.Timestamp(row.stage_anchor_timestamp_utc)).total_seconds()/3600, 2))
    gain = vectors["flood_gain.geojson"].geometry.union_all()
    assert np.array_equal(mask(gain), initial)
    zones = vectors["flood_gain_zones.geojson"]
    assert zones.zone_id.is_unique and zones.source_observation_id.eq("OBS01").all()
    close(zones.area_ha.sum(), 54.92)
    assert gain.symmetric_difference(zones.geometry.union_all()).area < 1e-6
    roads, bridges = tables["road_exposure.csv"], tables["bridge_exposure.csv"]
    assert roads.osm_id.is_unique and bridges.osm_id.is_unique
    close(roads.direct_intersection.sum(), 14)
    close(roads.flood_intersection_m.sum(), 345.7434178260874)
    close(bridges.direct_intersection.sum(), 1)
    for frame in (roads, bridges):
        assert frame.source_observation_id.eq("OBS01").all()
        assert frame.direct_intersection.eq(frame.flood_intersection_m.gt(0)).all()
        for distance in (50, 100, 250):
            assert frame[f"within_{distance}m"].eq(frame.distance_to_gain_m.le(distance)).all()
    road_geom = vectors["exposed_roads.geojson"]
    assert set(road_geom.osm_id) == set(roads.loc[roads.within_250m, "osm_id"])
    close(road_geom.geometry.intersection(gain).length, road_geom.flood_intersection_m)
    close(road_geom.geometry.distance(gain), road_geom.distance_to_gain_m)
    bc7 = bridges.loc[bridges.osm_id.eq(62001004)].iloc[0]
    close(bc7.flood_intersection_m, 8.717200334423737, atol=.001)
    assert bool(bc7.direct_intersection)
    taylor = bridges.loc[bridges.osm_id.eq(1346291619)].iloc[0]
    assert not bool(taylor.direct_intersection)
    close(taylor.distance_to_gain_m, 132.279286, atol=.001)
    alr = vectors["alr_gain_overlap.geojson"].geometry.union_all()
    assert alr.difference(gain.buffer(1e-7)).area < 1e-6
    close(alr.area/10000, 36.64518044420364)
    close(zones.alr_overlap_ha.sum(), alr.area/10000)
    priority = tables["priority_grid_impact.csv"]
    assert len(priority) == 9 and priority.grid_id.is_unique
    assert ((priority.event_gain_area_ha > 0) & ((priority.event_minus_baseline_pp > 5.88)
            | (priority.road_count_direct > 0) | (priority.bridge_count_direct > 0))).all()
    assert priority.grid_id.tolist() == priority.sort_values(
        ["event_minus_baseline_pp", "event_gain_area_ha"], ascending=False).grid_id.tolist()
    grid_geo = vectors["priority_grids.geojson"].set_index("grid_id")
    for row in priority.itertuples():
        cell_mask = mask(grid_geo.loc[row.grid_id].geometry)
        close(reference[cell_mask].mean()*100, row.baseline_water_ratio_pct)
        close((reference | initial)[cell_mask].mean()*100, row.event_water_ratio_pct)
        close((reference | final)[cell_mask].mean()*100, row.recovery_water_ratio_pct)
        close((initial & cell_mask).sum()*.04, row.event_gain_area_ha)
        close(row.event_water_ratio_pct-row.baseline_water_ratio_pct, row.event_minus_baseline_pp)
    close(priority.set_index("grid_id").loc["G042"].event_minus_baseline_pp, 21.5)
    close(priority.set_index("grid_id").loc["G015"].event_minus_baseline_pp, 6.78947368421052)
    places = tables["community_proximity.csv"]
    assert places.PNuid_NLidu.is_unique
    points = gpd.GeoSeries(gpd.points_from_xy(places.Longitude, places.Latitude), crs=4326).to_crs(32610)
    close(points.distance(gain), places.distance_to_gain_m)
    assert points.within(aoi).eq(places.inside_aoi).all()
    close(places.distance_to_gain_m.min(), 303.789764, atol=.001)
    trajectory = tables["event_trajectory.csv"].set_index("observation_id")
    assert len(trajectory) == 7
    close(trajectory.loc[obs.observation_id].flood_outside_baseline_ha, obs.egs_open_water_flood_ha)
    validation = json.loads((p4 / "recovery_validation.json").read_text())
    counts = validation["confusion_pixels"]
    tp, fp, fn, tn = [counts[k] for k in ("TP", "FP", "FN", "TN")]
    assert tp+fp+fn+tn == validation["evaluation_pixels"] == 88515
    metrics = {"precision": tp/(tp+fp), "recall": tp/(tp+fn),
               "F1": 2*tp/(2*tp+fp+fn), "IoU": tp/(tp+fp+fn)}
    for name, value in metrics.items():
        close(validation["metrics"][name], value)
    assert 6.2 < validation["temporal_offset_days"] < 6.21
    metrics_table = tables["final_case_metrics.csv"].set_index("metric")
    close(metrics_table.loc["Recovery RCM/Sentinel-2 F1", "value"], round(metrics["F1"], 3))
    close(metrics_table.loc["Recovery RCM/Sentinel-2 IoU", "value"], round(metrics["IoU"], 3))
    selected = method_selection(repo)
    assert audit["method_selection"] == handoff["method_selection"] == selected
    return {
        "status": "PASS",
        "production_source": selected["production_spatial_source"],
        "phase3b_status": selected["phase3b_status"],
        "grid": {"crs": "EPSG:32610", "shape": [300, 300], "pixel_size_m": 20, "pixel_area_ha": .04},
        "observations": obs[["observation_id", "timestamp_utc", "egs_open_water_flood_ha"]].to_dict("records"),
        "endpoint_metrics_ha": audit["endpoint_metrics_ha"],
        "roads": {"clipped_way_count": len(roads), "within_250m": int(roads.within_250m.sum()),
                  "direct_way_count": 14, "direct_length_m": float(roads.flood_intersection_m.sum())},
        "bridges": {"clipped_way_count": len(bridges), "direct_way_count": 1,
                    "within_250m": int(bridges.within_250m.sum()), "bc7_overlap_m": float(bc7.flood_intersection_m)},
        "alr_overlap_ha": alr.area/10000, "alr_share_of_initial_gain_pct": 100*alr.area/gain.area,
        "retained_priority_grids": priority.grid_id.tolist(),
        "recovery_comparison": validation,
        "scientific_outputs_recomputed": False,
        "checks": ["hashes and paths", "unique UTC observations", "20m geometry/mask/area contract",
                   "gross/net transition identities", "six adjacent and three beam-family comparisons",
                   "gauge extrema and timestamp alignment", "road/bridge/ALR/place geometry regression",
                   "priority coverage and selection", "compatibility views", "recovery count arithmetic", "frozen method selection"],
        "limits": ["No new Sentinel-2 processing: agreement counts audited against existing saved output",
                   "Full ALR input polygons are not retained; overlap geometry is reproducible, full ALR area is not",
                   "25 nearest place points retained, not a full inventory",
                   "Legacy baseline fields and human-readable GeoJSON date labels retained for compatibility"],
    }


if __name__ == "__main__":
    report = validate()
    print(json.dumps(report, indent=2, ensure_ascii=False) if "--json" in sys.argv else
          "PASS: offline Phase 4/5 geometry, temporal, exposure, provenance and frozen-source contracts")
