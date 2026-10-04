"""Offline-first Streamlit dashboard for the Earth in Motion case study."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "processed" / "phase5"
PHASE4_DIR = BASE_DIR / "data" / "processed" / "phase4"
MANIFEST_FILE = DATA_DIR / "phase6_handoff.json"

TABLE_FILES = {
    "metrics": "final_case_metrics.csv",
    "priority": "priority_grid_impact.csv",
    "roads": "road_exposure.csv",
    "bridges": "bridge_exposure.csv",
    "communities": "community_proximity.csv",
    "evidence": "evidence_chain.csv",
    "sources": "official_event_sources.csv",
    "limitations": "limitations.csv",
}
VECTOR_FILES = {
    "gain": "flood_gain.geojson",
    "zones": "flood_gain_zones.geojson",
    "priority_grids": "priority_grids.geojson",
    "roads": "exposed_roads.geojson",
    "alr": "alr_gain_overlap.geojson",
}
PHASE4_FILES = {
    "frames": "egs_open_water_flood_frames.geojson",
    "reference": "egs_permanent_water_reference.geojson",
    "observations": "event_observations.csv",
    "alignment": "rcm_stage_alignment.csv",
    "hydrology": "event_hydrology_unit_values.csv",
    "hydrologic_stages": "hydrologic_stage_summary.csv",
}

NAV_ITEMS = ("Overview", "Detect", "Map", "Monitor", "Impact", "Evidence & Method")
VALIDATION_METRICS = {"Precision": 0.663, "Recall": 0.978, "F1": 0.790, "IoU": 0.653}

PALETTES = {
    "light": {
        "text": "#17252d", "muted": "#53656e", "surface": "#ffffff", "surface_alt": "#f2f5f6",
        "border": "#d7e0e4", "hero": "#e7f2f5", "callout": "#fff5ed", "road": "#4d5860",
    },
    "dark": {
        "text": "#f4f7f8", "muted": "#b8c5ca", "surface": "#1d252b", "surface_alt": "#273139",
        "border": "#45535c", "hero": "#192d35", "callout": "#332a24", "road": "#c1ccd1",
    },
}

# Color is always accompanied by text, geometry, and tooltips.
COLORS = {
    "gain": [213, 94, 0],
    "alr": [0, 114, 178],
    "priority": [230, 159, 0],
    "bridge": [0, 158, 115],
    "community": [204, 121, 167],
    "road_light": [77, 88, 96],
    "road_dark": [193, 204, 209],
}

LAYER_META = {
    "gain": {"label": "Mapped flood gain", "group": "Observed change", "color": COLORS["gain"]},
    "gain_zones": {"label": "Flood-gain zones", "group": "Observed change", "color": COLORS["gain"]},
    "priority_grids": {"label": "Retained priority grids", "group": "Detection", "color": COLORS["priority"]},
    "grid_ids": {"label": "All retained grid IDs", "group": "Detection", "color": COLORS["priority"]},
    "hotspot_grids": {"label": "G042 and G015 hotspots", "group": "Detection", "color": COLORS["priority"]},
    "direct_roads": {"label": "Direct road intersections", "group": "Infrastructure exposure", "color": COLORS["road_light"]},
    "nearby_roads": {"label": "Roads within 250 m", "group": "Infrastructure exposure", "color": COLORS["road_light"]},
    "direct_bridge": {"label": "Direct bridge-tagged way", "group": "Infrastructure exposure", "color": COLORS["bridge"]},
    "nearby_bridge": {"label": "Nearby bridge-tagged way", "group": "Infrastructure exposure", "color": COLORS["bridge"]},
    "alr_overlap": {"label": "Mapped gain overlapping ALR designation", "group": "Land and place context", "color": COLORS["alr"]},
    "communities_inside": {"label": "Official place point inside AOI", "group": "Land and place context", "color": COLORS["community"]},
    "communities_all": {"label": "Other official place points", "group": "Land and place context", "color": COLORS["community"]},
}

MAP_PRESETS = {
    "overview": {
        "available": ("gain", "hotspot_grids"), "default": ("gain", "hotspot_grids"),
        "height": 400, "interactive": False, "show_controls": False, "show_technical": False,
    },
    "detection": {
        "available": ("gain", "priority_grids", "hotspot_grids", "grid_ids"),
        "default": ("gain", "priority_grids", "hotspot_grids"),
        "height": 480, "interactive": True, "show_controls": False, "show_technical": False,
    },
    "exploration": {
        "available": tuple(LAYER_META),
        "default": ("gain", "priority_grids", "hotspot_grids", "direct_roads"),
        "height": 610, "interactive": True, "show_controls": True, "show_technical": True,
    },
    "impact_infrastructure": {
        "available": ("gain", "direct_roads", "nearby_roads", "direct_bridge", "nearby_bridge"),
        "default": ("gain", "direct_roads", "direct_bridge"),
        "height": 540, "interactive": True, "show_controls": False, "show_technical": False,
    },
    "impact_agriculture": {
        "available": ("gain", "alr_overlap"), "default": ("gain", "alr_overlap"),
        "height": 540, "interactive": True, "show_controls": False, "show_technical": False,
    },
    "impact_community": {
        "available": ("gain", "communities_inside"), "default": ("gain", "communities_inside"),
        "height": 540, "interactive": True, "show_controls": False, "show_technical": False,
    },
}


def current_theme() -> tuple[str, dict[str, str]]:
    """Return the active Streamlit theme with a safe fallback for bare Python runs."""
    try:
        name = (st.context.theme.type or "light").lower()
    except Exception:
        name = "light"
    if name not in PALETTES:
        name = "light"
    return name, PALETTES[name]


THEME_NAME, THEME = current_theme()

st.set_page_config(
    page_title="Earth in Motion | Lower Fraser Flood",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    f"""
    <style>
    :root {{
        --eim-text: {THEME['text']}; --eim-muted: {THEME['muted']}; --eim-surface: {THEME['surface']};
        --eim-surface-alt: {THEME['surface_alt']}; --eim-border: {THEME['border']}; --eim-hero: {THEME['hero']};
        --eim-callout: {THEME['callout']};
    }}
    .block-container {{ padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1320px; }}
    .eim-hero {{ padding: 1.35rem 1.5rem; border-radius: .85rem; margin-bottom: 1.25rem; background: var(--eim-hero); border: 1px solid var(--eim-border); }}
    .eim-hero h1 {{ margin: 0 0 .2rem 0; color: var(--eim-text); font-size: 2.35rem; }}
    .eim-hero p {{ margin: .2rem 0; color: var(--eim-muted); font-size: 1.02rem; }}
    .eyebrow {{ font-size: .78rem; font-weight: 750; letter-spacing: .09em; text-transform: uppercase; color: #0072B2; }}
    .status-pill {{ display: inline-block; padding: .25rem .65rem; margin-top: .65rem; border-radius: 999px; background: rgba(0, 158, 115, .16); color: #009E73; font-weight: 700; font-size: .82rem; }}
    [data-testid="stMetric"] {{ border: 1px solid var(--eim-border); border-radius: .75rem; padding: .8rem 1rem; background: var(--eim-surface) !important; min-height: 110px; }}
    [data-testid="stMetricLabel"] {{ color: var(--eim-muted) !important; font-size: .86rem; line-height: 1.25; }}
    [data-testid="stMetricValue"] {{ color: var(--eim-text) !important; line-height: 1.15; }}
    [data-testid="stMetricDelta"] {{ color: #009E73 !important; }}
    .workflow-step {{ border-left: 3px solid #0072B2; padding: .2rem 0 .25rem .7rem; min-height: 98px; }}
    .workflow-step strong {{ color: #0072B2; }}
    .eim-callout {{ border-left: 4px solid #D55E00; background: var(--eim-callout); color: var(--eim-text); padding: .8rem 1rem; border-radius: .3rem; margin: .45rem 0 1rem 0; }}
    .source-card {{ padding: .65rem 0; border-bottom: 1px solid var(--eim-border); }}
    .small-note {{ color: var(--eim-muted); font-size: .86rem; }}
    .map-legend {{ display: flex; flex-wrap: wrap; gap: .55rem 1rem; align-items: center; padding: .55rem .75rem; margin: .35rem 0 .6rem 0; border: 1px solid var(--eim-border); border-radius: .55rem; background: var(--eim-surface-alt); color: var(--eim-text); font-size: .86rem; }}
    .legend-item {{ display: inline-flex; align-items: center; gap: .35rem; }}
    .legend-swatch {{ width: .85rem; height: .65rem; border-radius: .15rem; display: inline-block; }}
    .north-arrow {{ color: var(--eim-muted); font-weight: 700; white-space: nowrap; }}
    .player-status {{ display: inline-block; padding: .22rem .6rem; border-radius: 999px; background: var(--eim-surface-alt); border: 1px solid var(--eim-border); color: var(--eim-muted); font-weight: 700; font-size: .83rem; }}
    .player-readout {{ padding: .75rem .9rem; border: 1px solid var(--eim-border); border-radius: .65rem; background: var(--eim-surface-alt); color: var(--eim-text); margin: .45rem 0 .65rem 0; }}
    @media (max-width: 700px) {{
        .block-container {{ padding-left: 1rem; padding-right: 1rem; }} .eim-hero h1 {{ font-size: 1.9rem; }}
        [data-testid="stMetric"] {{ min-height: 96px; padding: .65rem .75rem; }} .workflow-step {{ min-height: auto; margin-bottom: .6rem; }}
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


def _expected_paths() -> list[Path]:
    return (
        [DATA_DIR / name for name in TABLE_FILES.values()]
        + [DATA_DIR / name for name in VECTOR_FILES.values()]
        + [PHASE4_DIR / name for name in PHASE4_FILES.values()]
        + [MANIFEST_FILE]
    )


def _file_signature(paths: list[Path]) -> tuple[tuple[str, int, int], ...]:
    """Make cached file reads refresh whenever a local handoff artifact changes."""
    return tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in paths)


@st.cache_data(show_spinner=False)
def load_tables(signature: tuple[tuple[str, int, int], ...]) -> dict[str, pd.DataFrame]:
    del signature
    return {key: pd.read_csv(DATA_DIR / filename) for key, filename in TABLE_FILES.items()}


@st.cache_data(show_spinner=False)
def load_vectors(signature: tuple[tuple[str, int, int], ...]) -> dict[str, gpd.GeoDataFrame]:
    del signature
    vectors = {key: gpd.read_file(DATA_DIR / filename) for key, filename in VECTOR_FILES.items()}
    for name, frame in vectors.items():
        if frame.crs is None or frame.crs.to_epsg() != 32610:
            raise ValueError(f"{name} must use EPSG:32610; found {frame.crs}")
    return vectors


@st.cache_data(show_spinner=False)
def load_manifest(signature: tuple[tuple[str, int, int], ...]) -> dict[str, Any]:
    del signature
    return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def load_acquisition_data(signature: tuple[tuple[str, int, int], ...]) -> dict[str, Any]:
    """Load canonical Phase 4 observations, hydrology, and map geometries."""
    del signature
    frames = gpd.read_file(PHASE4_DIR / PHASE4_FILES["frames"])
    reference = gpd.read_file(PHASE4_DIR / PHASE4_FILES["reference"])
    observations = pd.read_csv(PHASE4_DIR / PHASE4_FILES["observations"])
    alignment = pd.read_csv(PHASE4_DIR / PHASE4_FILES["alignment"])
    hydrology = pd.read_csv(PHASE4_DIR / PHASE4_FILES["hydrology"])
    hydrologic_stages = pd.read_csv(PHASE4_DIR / PHASE4_FILES["hydrologic_stages"])
    hydrology["timestamp_utc"] = pd.to_datetime(hydrology["timestamp_utc"], utc=True)
    for column in ("start_utc", "end_utc", "anchor_timestamp_utc"):
        hydrologic_stages[column] = pd.to_datetime(hydrologic_stages[column], utc=True)
    for name, frame in {"frames": frames, "reference": reference}.items():
        if frame.crs is None or frame.crs.to_epsg() != 32610:
            raise ValueError(f"{name} must use EPSG:32610; found {frame.crs}")
    return {
        "frames": frames,
        "reference": reference,
        "observations": observations,
        "alignment": alignment,
        "hydrology": hydrology,
        "hydrologic_stages": hydrologic_stages,
    }


def _require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required fields: {', '.join(missing)}")


def build_temporal_contract(acquisition: dict[str, Any]) -> pd.DataFrame:
    """Build one canonical seven-row Dashboard view from Phase 4 source-of-truth files."""
    observations = acquisition["observations"].copy()
    alignment = acquisition["alignment"].copy()
    _require_columns(
        observations,
        {
            "observation_id", "timestamp_utc", "platform", "beam_mode", "source_resolution_m",
            "orbit_direction", "swath_radiometry", "classifier_channel", "confidence",
            "egs_open_water_flood_ha", "fixed_reference_total_water_ha",
        },
        "Phase 4 event_observations.csv",
    )
    _require_columns(
        alignment,
        {"observation_id", "stage_id", "stage_label", "observation_role", "caveat"},
        "Phase 4 rcm_stage_alignment.csv",
    )
    alignment_fields = [
        "observation_id", "stage_id", "stage_label", "observation_role",
        "stage_anchor_timestamp_utc", "offset_to_stage_anchor_hours", "caveat",
    ]
    available_alignment_fields = [field for field in alignment_fields if field in alignment.columns]
    trajectory = observations.merge(
        alignment[available_alignment_fields],
        on="observation_id",
        how="left",
        validate="one_to_one",
    ).rename(columns={"egs_open_water_flood_ha": "flood_outside_baseline_ha"})
    trajectory["timestamp_utc"] = pd.to_datetime(trajectory["timestamp_utc"], utc=True)
    trajectory = trajectory.sort_values("timestamp_utc").reset_index(drop=True)
    if len(trajectory) != 7 or trajectory["observation_id"].nunique() != 7:
        raise ValueError("The Phase 4 temporal contract must contain seven unique observations.")
    if trajectory[["stage_id", "stage_label", "observation_role", "caveat"]].isna().any().any():
        raise ValueError("Every Phase 4 observation must have a hydrologic-stage alignment record.")
    return trajectory


def metric_number(metrics: pd.DataFrame, name: str) -> float:
    row = metrics.loc[metrics["metric"].eq(name), "value"]
    if row.empty:
        raise KeyError(f"Required metric is missing: {name}")
    return float(row.iloc[0])


def render_header(section: str, description: str) -> None:
    st.markdown(f'<div class="eyebrow">Earth in Motion · {section}</div>', unsafe_allow_html=True)
    st.title(section)
    st.write(description)


def render_metric_rows(items: list[tuple[str, str, str | None]]) -> None:
    """Render no more than three metrics per row so values remain readable."""
    for start in range(0, len(items), 3):
        row = items[start : start + 3]
        for column, (label, value, delta) in zip(st.columns(len(row)), row):
            with column:
                st.metric(label, value, delta)


def _feature_collection(frame: gpd.GeoDataFrame) -> dict[str, Any]:
    # Phase 4 frame metadata includes pandas timestamps; GeoJSON properties must be JSON-safe.
    return json.loads(frame.to_json(default=str))


def _road_label(row: pd.Series) -> str:
    name = str(row["name"]) if pd.notna(row.get("name")) else f"OSM way {int(row['osm_id'])}"
    ref = str(row["ref"]) if pd.notna(row.get("ref")) else ""
    return f"{name} / {ref}" if ref else name


def _tooltip(title: str, lines: list[str]) -> str:
    return f"<b>{title}</b><br>" + "<br>".join(lines)


def _decorate_map_data(vectors: dict[str, gpd.GeoDataFrame], tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Prepare small local layer subsets and tooltip text without changing source files."""
    metrics = tables["metrics"]
    gain_ha = metric_number(metrics, "Mapped event water gain")
    alr_ha = metric_number(metrics, "Mapped gain intersecting ALR")
    priority = tables["priority"]

    grids = vectors["priority_grids"].merge(
        priority[["grid_id", "recovery_water_ratio_pct", "road_count_direct", "bridge_count_direct", "alr_overlap_ha"]],
        on="grid_id",
        how="left",
    ).copy()
    grids["tooltip"] = grids.apply(
        lambda row: _tooltip(
            f"Grid {row.grid_id}",
            [
                f"Increase: {row.event_minus_baseline_pp:.2f} pp",
                f"Mapped gain: {row.event_gain_area_ha:.2f} ha",
                f"Recovery water: {row.recovery_water_ratio_pct:.2f}%",
                f"Interpretation: {row.interpretation}",
            ],
        ),
        axis=1,
    )

    zones = vectors["zones"].copy()
    zones["tooltip"] = zones.apply(
        lambda row: _tooltip(
            f"Flood-gain zone {row.zone_id}",
            [
                f"Area: {row.area_ha:.2f} ha",
                f"ALR overlap: {row.alr_overlap_ha:.2f} ha",
                f"Direct road ways: {int(row.road_count_direct)}",
                f"Nearest place: {row.nearest_community}",
            ],
        ),
        axis=1,
    )

    gain = vectors["gain"].copy()
    gain["tooltip"] = _tooltip("Mapped flood gain", [f"Area: {gain_ha:.2f} ha", "Water mapped outside the local semantic baseline."])

    alr = vectors["alr"].copy()
    alr["tooltip"] = _tooltip(
        "Mapped gain overlapping ALR designation",
        [f"Mapped overlap: {alr_ha:.2f} ha", "ALR is a land designation, not a crop map."],
    )

    roads = vectors["roads"].copy()
    roads["road_label"] = roads.apply(_road_label, axis=1)
    direct = roads.loc[roads["direct_intersection"].fillna(False)].copy()
    nearby = roads.loc[~roads["direct_intersection"].fillna(False)].copy()
    direct["tooltip"] = direct.apply(
        lambda row: _tooltip(
            row.road_label,
            [
                f"OSM way: {int(row.osm_id)}",
                f"Class: {row.highway}",
                f"Direct mapped intersection: {row.flood_intersection_m:.2f} m",
            ],
        ),
        axis=1,
    )
    nearby["tooltip"] = nearby.apply(
        lambda row: _tooltip(
            row.road_label,
            [f"OSM way: {int(row.osm_id)}", f"Class: {row.highway}", f"Distance to mapped gain: {row.distance_to_gain_m:.1f} m"],
        ),
        axis=1,
    )

    bridge_mask = roads["bridge"].fillna("").astype(str).str.lower().eq("yes")
    direct_bridge = roads.loc[bridge_mask & roads["direct_intersection"].fillna(False)].copy()
    nearby_bridge = roads.loc[bridge_mask & ~roads["direct_intersection"].fillna(False)].copy()
    direct_bridge["tooltip"] = direct_bridge.apply(
        lambda row: _tooltip(
            f"{row.road_label} bridge-tagged way",
            [
                "Relationship: direct mapped intersection",
                f"Geometric overlap: {row.flood_intersection_m:.2f} m",
                "Potential exposure only; this does not establish structural damage.",
            ],
        ),
        axis=1,
    )
    nearby_bridge["tooltip"] = nearby_bridge.apply(
        lambda row: _tooltip(
            f"{row.road_label} bridge-tagged way",
            [
                "Relationship: nearby mapped gain",
                f"Distance to mapped gain: {row.distance_to_gain_m:.1f} m",
                "Potential exposure only; this does not establish structural damage.",
            ],
        ),
        axis=1,
    )

    marker = gpd.GeoDataFrame(columns=["label", "tooltip", "geometry"], geometry="geometry", crs=roads.crs)
    if not direct_bridge.empty:
        direct_geometry = direct_bridge.geometry.iloc[0]
        gain_geometry = gain.geometry.union_all()
        overlap = direct_geometry.intersection(gain_geometry)
        location = overlap.representative_point() if not overlap.is_empty else direct_geometry.representative_point()
        marker = gpd.GeoDataFrame(
            {
                "label": ["BC 7 bridge-tagged way"],
                "tooltip": [_tooltip("BC 7 bridge-tagged way", ["Direct mapped geometric overlap: 8.72 m", "Potential exposure only; no structural damage is inferred."])],
            },
            geometry=[location],
            crs=roads.crs,
        )

    communities = tables["communities"].copy()
    communities["geometry"] = gpd.points_from_xy(communities["Longitude"], communities["Latitude"])
    community_frame = gpd.GeoDataFrame(communities, geometry="geometry", crs="EPSG:4326").to_crs(roads.crs)
    community_frame["tooltip"] = community_frame.apply(
        lambda row: _tooltip(
            str(row.place_name),
            [f"Inside AOI: {'Yes' if row.inside_aoi else 'No'}", f"Distance to mapped gain: {row.distance_to_gain_m:.1f} m", "Official place point; not a population estimate."],
        ),
        axis=1,
    )
    community_frame["label"] = community_frame["place_name"]

    projected = {
        "gain": gain,
        "gain_zones": zones,
        "priority_grids": grids,
        "hotspot_grids": grids.loc[grids["grid_id"].isin(["G042", "G015"])].copy(),
        "direct_roads": direct,
        "nearby_roads": nearby,
        "direct_bridge": direct_bridge,
        "nearby_bridge": nearby_bridge,
        "bridge_marker": marker,
        "alr_overlap": alr,
        "communities_inside": community_frame.loc[community_frame["inside_aoi"]].copy(),
        "communities_all": community_frame.loc[~community_frame["inside_aoi"]].copy(),
    }
    prepared: dict[str, Any] = {name: frame.to_crs(4326) for name, frame in projected.items()}
    prepared["grid_labels"] = _label_records(prepared["priority_grids"])
    prepared["hotspot_labels"] = _label_records(prepared["hotspot_grids"])
    prepared["bridge_labels"] = _point_records(prepared["bridge_marker"])
    prepared["community_inside_points"] = _point_records(prepared["communities_inside"])
    prepared["community_all_points"] = _point_records(prepared["communities_all"])
    return prepared


def _label_records(frame: gpd.GeoDataFrame) -> list[dict[str, Any]]:
    points = frame.representative_point()
    return [{"position": [float(point.x), float(point.y)], "label": str(row.grid_id)} for point, (_, row) in zip(points, frame.iterrows())]


def _point_records(frame: gpd.GeoDataFrame) -> list[dict[str, Any]]:
    return [
        {"position": [float(point.x), float(point.y)], "label": str(row["label"]), "tooltip": str(row["tooltip"])}
        for point, (_, row) in zip(frame.geometry, frame.iterrows())
    ]


def _geojson_layer(frame: gpd.GeoDataFrame, *, fill: list[int] | None = None, line: list[int], width: int) -> pdk.Layer:
    return pdk.Layer(
        "GeoJsonLayer",
        data=_feature_collection(frame),
        pickable=True,
        auto_highlight=True,
        stroked=True,
        filled=fill is not None,
        get_fill_color=fill or [0, 0, 0, 0],
        get_line_color=line,
        get_line_width=width,
        line_width_min_pixels=1,
    )


def _text_layer(records: list[dict[str, Any]], color: list[int], *, size: int = 14) -> pdk.Layer:
    return pdk.Layer(
        "TextLayer",
        data=records,
        pickable=False,
        get_position="position",
        get_text="label",
        get_size=size,
        get_color=color,
        get_text_anchor="middle",
        get_alignment_baseline="center",
    )


def _point_layer(records: list[dict[str, Any]], color: list[int], *, radius: int) -> pdk.Layer:
    return pdk.Layer(
        "ScatterplotLayer",
        data=records,
        pickable=True,
        get_position="position",
        get_radius=radius,
        get_fill_color=color + [225],
        get_line_color=color + [255],
        line_width_min_pixels=2,
    )


def build_map_layers(prepared: dict[str, Any], active_layers: set[str]) -> list[pdk.Layer]:
    """Build only the selected layers, in a stable visual order."""
    road_color = COLORS["road_light"] if THEME_NAME == "light" else COLORS["road_dark"]
    layers: list[pdk.Layer] = []
    if "gain" in active_layers:
        layers.append(_geojson_layer(prepared["gain"], fill=COLORS["gain"] + [85], line=COLORS["gain"] + [235], width=2))
    if "gain_zones" in active_layers:
        layers.append(_geojson_layer(prepared["gain_zones"], fill=COLORS["gain"] + [35], line=COLORS["gain"] + [215], width=1))
    if "alr_overlap" in active_layers:
        layers.append(_geojson_layer(prepared["alr_overlap"], fill=COLORS["alr"] + [165], line=COLORS["alr"] + [255], width=3))
    if "nearby_roads" in active_layers:
        layers.append(_geojson_layer(prepared["nearby_roads"], line=road_color + [170], width=2))
    if "direct_roads" in active_layers:
        layers.append(_geojson_layer(prepared["direct_roads"], line=road_color + [255], width=5))
    if "priority_grids" in active_layers:
        layers.append(_geojson_layer(prepared["priority_grids"], fill=COLORS["priority"] + [12], line=COLORS["priority"] + [220], width=3))
    if "hotspot_grids" in active_layers:
        layers.append(_geojson_layer(prepared["hotspot_grids"], fill=COLORS["priority"] + [36], line=COLORS["priority"] + [255], width=7))
        layers.append(_text_layer(prepared["hotspot_labels"], COLORS["priority"] + [255], size=16))
    if "grid_ids" in active_layers:
        layers.append(_text_layer(prepared["grid_labels"], COLORS["priority"] + [255], size=13))
    if "nearby_bridge" in active_layers:
        layers.append(_geojson_layer(prepared["nearby_bridge"], line=COLORS["bridge"] + [205], width=5))
    if "direct_bridge" in active_layers:
        layers.append(_geojson_layer(prepared["direct_bridge"], line=COLORS["bridge"] + [255], width=8))
        if prepared["bridge_labels"]:
            layers.append(_point_layer(prepared["bridge_marker"].assign(label="BC 7 bridge-tagged way").pipe(_point_records), COLORS["bridge"], radius=105))
            layers.append(_text_layer(prepared["bridge_labels"], COLORS["bridge"] + [255], size=14))
    if "communities_all" in active_layers:
        layers.append(_point_layer(prepared["community_all_points"], COLORS["community"], radius=70))
    elif "communities_inside" in active_layers:
        layers.append(_point_layer(prepared["community_inside_points"], COLORS["community"], radius=90))
    return layers


def _map_view_state(prepared: dict[str, Any]) -> pdk.ViewState:
    min_x, min_y, max_x, max_y = prepared["gain"].total_bounds
    return pdk.ViewState(longitude=float((min_x + max_x) / 2), latitude=float((min_y + max_y) / 2), zoom=11.2, pitch=0, bearing=0)


def build_local_deck(prepared: dict[str, Any], preset_name: str, active_layers: set[str], wheel_zoom: bool = False) -> pdk.Deck:
    preset = MAP_PRESETS[preset_name]
    controller: bool | dict[str, bool]
    if preset["interactive"]:
        controller = {"dragPan": True, "doubleClickZoom": True, "touchZoom": True, "scrollZoom": wheel_zoom}
    else:
        controller = False
    return pdk.Deck(
        layers=build_map_layers(prepared, active_layers),
        views=[pdk.View(type="MapView", controller=controller)],
        map_style="",
        map_provider=None,
        initial_view_state=_map_view_state(prepared),
        height=MAP_PRESETS[preset_name]["height"],
        tooltip={"html": "{tooltip}", "style": {"backgroundColor": THEME["surface_alt"], "color": THEME["text"], "fontSize": "12px"}},
    )


def render_map_legend(active_layers: set[str]) -> None:
    items = [LAYER_META[layer_id] for layer_id in LAYER_META if layer_id in active_layers]
    if not items:
        return
    swatches = "".join(
        f'<span class="legend-item"><span class="legend-swatch" style="background: rgb({meta["color"][0]},{meta["color"][1]},{meta["color"][2]});"></span>{meta["label"]}</span>'
        for meta in items
    )
    st.markdown(f'<div class="map-legend">{swatches}<span class="north-arrow">N ↑</span></div>', unsafe_allow_html=True)


def _restore_map_defaults(key: str, defaults: tuple[str, ...]) -> None:
    st.session_state[f"{key}-layers"] = list(defaults)
    st.session_state[f"{key}-wheel"] = False
    st.session_state[f"{key}-revision"] = st.session_state.get(f"{key}-revision", 0) + 1


def _map_controls(preset_name: str, key: str) -> tuple[set[str], bool, int]:
    preset = MAP_PRESETS[preset_name]
    available = list(preset["available"])
    defaults = list(preset["default"])
    layers_key = f"{key}-layers"
    wheel_key = f"{key}-wheel"
    if layers_key not in st.session_state:
        st.session_state[layers_key] = defaults
    if wheel_key not in st.session_state:
        st.session_state[wheel_key] = False

    layer_column, settings_column = st.columns([5, 1])
    with layer_column:
        selected = st.multiselect(
            "Visible layers",
            options=available,
            format_func=lambda layer_id: LAYER_META[layer_id]["label"],
            key=layers_key,
            help="Choose any combination of local layers to display.",
        )

    with settings_column:
        with st.popover("Map settings"):
            wheel_zoom = st.checkbox(
                "Mouse-wheel zoom",
                key=wheel_key,
                help="Off by default so normal page scrolling remains predictable.",
            )
            if st.button("Reset map view", key=f"{key}-reset", use_container_width=True):
                st.session_state[f"{key}-revision"] = st.session_state.get(f"{key}-revision", 0) + 1
            st.button(
                "Restore default layers",
                key=f"{key}-defaults",
                use_container_width=True,
                on_click=_restore_map_defaults,
                args=(key, tuple(defaults)),
            )

    return set(selected), wheel_zoom, st.session_state.get(f"{key}-revision", 0)


def render_map(prepared: dict[str, Any], preset_name: str, key: str, *, active_layers: set[str] | None = None, wheel_zoom: bool = False) -> None:
    preset = MAP_PRESETS[preset_name]
    revision = st.session_state.get(f"{key}-revision", 0)
    if preset["show_controls"]:
        active_layers, wheel_zoom, revision = _map_controls(preset_name, key)
    elif active_layers is None:
        active_layers = set(preset["default"])
    assert active_layers is not None
    if not active_layers:
        st.info("Select at least one layer to display the local map.")
        return
    render_map_legend(active_layers)
    deck = build_local_deck(prepared, preset_name, active_layers, wheel_zoom)
    st.pydeck_chart(deck, width="stretch", height=preset["height"], key=f"{key}-deck-{revision}")
    if preset["show_technical"]:
        with st.expander("Technical coordinates"):
            st.caption("Rendered coordinates: WGS84 / EPSG:4326. Analytical layers and reported areas use EPSG:32610.")


def prepare_acquisition_frames(acquisition: dict[str, Any]) -> dict[str, gpd.GeoDataFrame]:
    """Decorate the seven Phase 4 EGS frames for the local, discrete-step player."""
    trajectory = acquisition["trajectory"].copy()
    frames = acquisition["frames"].merge(
        trajectory[
            [
                "observation_id", "timestamp_utc", "platform", "beam_mode", "source_resolution_m",
                "orbit_direction", "swath_radiometry", "classifier_channel", "confidence",
                "flood_outside_baseline_ha", "stage_id", "stage_label", "observation_role", "caveat",
            ]
        ],
        on="observation_id",
        how="left",
        suffixes=("_frame", ""),
    ).sort_values("timestamp_utc")
    frames["tooltip"] = frames.apply(
        lambda row: _tooltip(
            f"{row.observation_id} · EGS open-water flood class",
            [
                f"Acquired: {pd.Timestamp(row.timestamp_utc).strftime('%d %b %Y %H:%M UTC')}",
                f"Mapped area: {row.flood_outside_baseline_ha:.2f} ha",
                f"Stage: {row.stage_label}",
                f"Platform / beam: {row.platform} · {row.beam_mode}",
                f"Resolution / orbit: {row.source_resolution_m:.0f} m · {row.orbit_direction}",
                f"Role: {row.observation_role}",
            ],
        ),
        axis=1,
    )
    reference = acquisition["reference"].copy()
    reference["tooltip"] = _tooltip(
        "Fixed EGS permanent-water reference",
        [
            "OBS01 product class 1 used for fixed semantic accounting.",
            "It is not an independently observed pre-event normal-water surface.",
        ],
    )
    return {"frames": frames.to_crs(4326), "reference": reference.to_crs(4326)}


def build_acquisition_deck(
    prepared: dict[str, Any],
    acquisition: dict[str, gpd.GeoDataFrame],
    frame_index: int,
    *,
    show_reference: bool,
    show_context: bool,
) -> pdk.Deck:
    """Build a local north-up deck for one observed acquisition, never an interpolated frame."""
    frame = acquisition["frames"].iloc[[frame_index]]
    layers: list[pdk.Layer] = []
    if show_reference:
        layers.append(_geojson_layer(acquisition["reference"], fill=[105, 132, 145, 42], line=[105, 132, 145, 205], width=1))
    if show_context:
        layers.extend(build_map_layers(prepared, {"priority_grids", "hotspot_grids", "direct_roads"}))
    layers.append(_geojson_layer(frame, fill=COLORS["gain"] + [145], line=COLORS["gain"] + [255], width=3))
    return pdk.Deck(
        layers=layers,
        views=[pdk.View(type="MapView", controller={"dragPan": True, "doubleClickZoom": True, "touchZoom": True, "scrollZoom": False})],
        map_style="",
        map_provider=None,
        initial_view_state=_map_view_state(prepared),
        height=555,
        tooltip={"html": "{tooltip}", "style": {"backgroundColor": THEME["surface_alt"], "color": THEME["text"], "fontSize": "12px"}},
    )


@st.fragment
def _render_acquisition_player_fragment(prepared: dict[str, Any], frame_data: dict[str, gpd.GeoDataFrame]) -> None:
    """Advance one observed frame per fragment rerun with one shared scrubber."""
    frames = frame_data["frames"].reset_index(drop=True)
    count = len(frames)
    index_key = "acquisition-player-index"
    playing_key = "acquisition-player-playing"
    scrubber_key = "acquisition-player-scrubber"
    if index_key not in st.session_state:
        st.session_state[index_key] = 0
    if playing_key not in st.session_state:
        st.session_state[playing_key] = False

    current_index = min(max(int(st.session_state[index_key]), 0), count - 1)
    playing = bool(st.session_state[playing_key])
    completed = playing and current_index >= count - 1
    if completed:
        playing = False
        st.session_state[playing_key] = False

    play_column, reset_column, layer_column, scrubber_column = st.columns([1.25, 1.15, 1.2, 4.4], vertical_alignment="bottom")
    with play_column:
        play_once = st.button(
            "▶ Play one pass",
            key="acquisition-player-play",
            use_container_width=True,
            disabled=playing,
            help="Always plays OBS01 through OBS07 once, then pauses at OBS07.",
        )
    with reset_column:
        reset = st.button("Reset to OBS01", key="acquisition-player-reset", use_container_width=True, disabled=playing)

    if play_once:
        current_index = 0
        playing = True
        st.session_state[index_key] = 0
        st.session_state[playing_key] = True
    elif reset:
        current_index = 0
        playing = False
        st.session_state[index_key] = 0
        st.session_state[playing_key] = False

    with layer_column:
        with st.popover("Map layers", use_container_width=True):
            context_enabled = st.checkbox("Priority grids and direct roads", value=True, key="acquisition-player-context")
            reference_enabled = st.checkbox("Fixed semantic water reference", value=False, key="acquisition-player-reference")

    options = list(range(count))
    labels = [f"{row.observation_id} · {pd.Timestamp(row.timestamp_utc).strftime('%d %b %H:%M UTC')}" for row in frames.itertuples()]
    if playing or play_once or reset or completed or scrubber_key not in st.session_state:
        st.session_state[scrubber_key] = current_index
    with scrubber_column:
        selected_index = st.select_slider(
            "Observed RCM frame",
            options=options,
            format_func=lambda index: labels[index],
            key=scrubber_key,
            disabled=playing,
            help="Drag to any real acquisition. Playback advances through these seven observed frames only.",
        )
    if not playing:
        current_index = selected_index
        st.session_state[index_key] = current_index

    status = f"Playing {current_index + 1} of {count}" if playing else f"Paused at {current_index + 1} of {count}"
    row = frames.iloc[current_index]
    timestamp = pd.Timestamp(row.timestamp_utc).strftime("%d %b %Y · %H:%M UTC")
    st.markdown(
        f'<div class="player-readout"><span class="player-status">{status}</span> '
        f'<strong>{row.observation_id} · {row.stage_label}</strong> · {timestamp}<br>'
        f'<strong>{row.flood_outside_baseline_ha:.2f} ha</strong> mapped EGS open-water flood class · '
        f'{row.platform} · {row.beam_mode} · {row.source_resolution_m:.0f} m · {row.observation_role}</div>',
        unsafe_allow_html=True,
    )

    legend = '<div class="map-legend"><span class="legend-item"><span class="legend-swatch" style="background:#D55E00"></span>Current EGS open-water flood class</span>'
    if reference_enabled:
        legend += '<span class="legend-item"><span class="legend-swatch" style="background:#698491"></span>Fixed semantic water reference</span>'
    if context_enabled:
        legend += '<span class="legend-item"><span class="legend-swatch" style="background:#E69F00"></span>Priority grids</span><span class="legend-item"><span class="legend-swatch" style="background:#4D5860"></span>Direct road intersections</span>'
    legend += '<span class="north-arrow">N ↑</span></div>'
    st.markdown(legend, unsafe_allow_html=True)

    deck = build_acquisition_deck(prepared, frame_data, current_index, show_reference=reference_enabled, show_context=context_enabled)
    st.pydeck_chart(deck, width="stretch", height=555, key="acquisition-player-deck")
    with st.expander("Current-frame interpretation"):
        st.caption(row.caveat)

    if playing and current_index < count - 1:
        st.session_state[index_key] = current_index + 1
        time.sleep(0.7)
        run_context = get_script_run_ctx(suppress_warning=True)
        if run_context is not None and run_context.fragment_ids_this_run:
            st.rerun(scope="fragment")


def render_acquisition_player(prepared: dict[str, Any], acquisition: dict[str, Any]) -> None:
    """Render a deliberately finite, user-controlled seven-observation playback."""
    st.subheader("Observed acquisition-step player")
    st.caption("Seven locally stored RCM-derived EGS observations, beginning with OBS01 on 12 Dec. Drag the single timeline or play one complete pass; no daily frame or interpolated flood geometry is generated.")
    _render_acquisition_player_fragment(prepared, prepare_acquisition_frames(acquisition))


def render_workflow_summary() -> None:
    st.subheader("How this case was built")
    steps = [
        ("1 · Observe", "Seven NRCan EGS RCM observations, 12–21 Dec."),
        ("2 · Detect", "Map open water outside the local semantic baseline on a 20 m grid."),
        ("3 · Compare", "Measure initial-observation gain, 1 km-grid change, and the discrete acquisition sequence."),
        ("4 · Validate", "Check recovery-period agreement with Sentinel-2."),
        ("5 · Contextualize", "Overlay roads, bridge-tagged ways, ALR designation, and place points."),
    ]
    for column, (title, text) in zip(st.columns(5), steps):
        column.markdown(f'<div class="workflow-step"><strong>{title}</strong><br><span class="small-note">{text}</span></div>', unsafe_allow_html=True)
    st.caption("See Evidence & Method for validation details, assumptions, and limitations.")


def render_overview(tables: dict[str, pd.DataFrame], prepared: dict[str, Any]) -> None:
    metrics = tables["metrics"]
    gain = metric_number(metrics, "Mapped event water gain")
    local_increase = metric_number(metrics, "Maximum local increase (G042)")
    gross_recession = metric_number(metrics, "Near-event to recovery mapped loss")
    roads = int(metric_number(metrics, "Directly intersecting road ways"))
    alr = metric_number(metrics, "Mapped gain intersecting ALR")
    alr_share = 100 * alr / gain
    st.markdown('<div class="eim-hero"><div class="eyebrow">December 2025 · Fraser Valley / Lower Fraser flood</div><h1>Earth in Motion</h1><p>Tracking flood evolution in the Lower Fraser using RCM and supporting Earth observation data</p><span class="status-pill">Recovering flood · localized residual expansion remains</span></div>', unsafe_allow_html=True)
    render_metric_rows([
        ("Mapped flood gain", f"{gain:.2f} ha", None),
        ("Largest 1 km-grid increase", f"+{local_increase:.2f} pp", None),
        ("Gross recession from initial footprint", f"{gross_recession:.2f} ha", None),
        ("Road ways intersecting mapped gain", f"{roads} ways", None),
        ("Gain overlapping ALR designation", f"{alr:.2f} ha", f"{alr_share:.1f}% of gain"),
    ])
    st.caption("Potential exposure only. ALR overlap indicates land designation, not crop loss.")
    render_workflow_summary()
    st.subheader("Event overview")
    render_map(prepared, "overview", "overview-map")
    st.caption("The overview map shows mapped gain and the two strongest retained hotspots, G042 and G015.")


def _hotspot_comparison(priority: pd.DataFrame) -> go.Figure:
    stage_labels = ["Baseline", "Near-event", "Recovery"]
    stage_dates = ["Reference class", "12 Dec", "21 Dec"]
    figure = go.Figure()
    for grid_id, color in (("G042", "#D55E00"), ("G015", "#0072B2")):
        row = priority.loc[priority["grid_id"].eq(grid_id)].iloc[0]
        values = [row.baseline_water_ratio_pct, row.event_water_ratio_pct, row.recovery_water_ratio_pct]
        figure.add_trace(go.Scatter(
            x=stage_labels,
            y=values,
            mode="lines+markers",
            name=grid_id,
            line={"color": color, "width": 3},
            marker={"size": 10, "color": color},
            customdata=[[stage_dates[index], value - values[0]] for index, value in enumerate(values)],
            hovertemplate="<b>%{fullData.name}</b><br>%{x} · %{customdata[0]}<br>Water coverage: %{y:.2f}%<br>Change from baseline: %{customdata[1]:+.2f} pp<extra></extra>",
        ))
    figure.update_layout(
        height=360,
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
        hovermode="closest",
        dragmode=False,
        yaxis={"title": "Water coverage (%)", "fixedrange": True, "range": [0, 50]},
        xaxis={"fixedrange": True},
        legend={"orientation": "h", "y": 1.12},
    )
    return figure


def render_detect(tables: dict[str, pd.DataFrame], prepared: dict[str, Any]) -> None:
    render_header("Detect", "Where did meaningful water expansion occur?")
    priority = tables["priority"].copy()
    g042 = priority.loc[priority["grid_id"].eq("G042")].iloc[0]
    g015 = priority.loc[priority["grid_id"].eq("G015")].iloc[0]
    st.write("G042 is the strongest observed expansion; G015 is the second retained grid above the Folly Lake empirical control-site context.")
    render_metric_rows([
        ("G042 increase", f"+{g042.event_minus_baseline_pp:.2f} pp", None),
        ("G015 increase", f"+{g015.event_minus_baseline_pp:.2f} pp", None),
        ("Cells above empirical context", "2", None),
    ])
    st.subheader("Retained change hotspots")
    render_map(prepared, "detection", "detect-map")
    st.subheader("Local water-coverage comparison")
    st.plotly_chart(_hotspot_comparison(priority), width="stretch", theme="streamlit", config={"displaylogo": False, "displayModeBar": False, "scrollZoom": False, "doubleClick": False, "responsive": True})
    st.subheader("Retained relevant grids")
    display_columns = {
        "grid_id": "Grid", "baseline_water_ratio_pct": "Baseline (%)", "event_water_ratio_pct": "Near-event (%)",
        "recovery_water_ratio_pct": "Recovery (%)", "event_minus_baseline_pp": "Increase (pp)",
        "event_gain_area_ha": "Gain (ha)", "interpretation": "Interpretation",
    }
    display = priority[list(display_columns)].rename(columns=display_columns)
    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={
            "Baseline (%)": st.column_config.NumberColumn(format="%.2f%%"),
            "Near-event (%)": st.column_config.NumberColumn(format="%.2f%%"),
            "Recovery (%)": st.column_config.NumberColumn(format="%.2f%%"),
            "Increase (pp)": st.column_config.NumberColumn(format="%.2f pp"),
            "Gain (ha)": st.column_config.NumberColumn(format="%.2f ha"),
            "Interpretation": st.column_config.TextColumn(width="large"),
        },
    )
    st.markdown('<div class="eim-callout"><strong>5.88 pp</strong> is an empirical control-site context from Folly Lake. It is not a universal flood threshold or a statistical significance test.</div>', unsafe_allow_html=True)


def render_map_page(prepared: dict[str, Any], acquisition: dict[str, Any]) -> None:
    render_header("Map", "How did the mapped RCM-derived flood extent change across the seven observed acquisitions?")
    render_acquisition_player(prepared, acquisition)
    with st.expander("Open the full static layer explorer"):
        st.caption("Optional: compare the change, infrastructure, designation, and place-context layers. All layers are local and no online basemap is requested.")
        render_map(prepared, "exploration", "map-page")


def _monitor_figure(
    trajectory: pd.DataFrame,
    hydrology: pd.DataFrame,
    hydrologic_stages: pd.DataFrame,
) -> go.Figure:
    """Combine continuous regional discharge and discrete RCM observations on one UTC axis."""
    dates = trajectory["timestamp_utc"]
    values = trajectory["flood_outside_baseline_ha"]
    discharge = hydrology.loc[
        hydrology["station_id"].eq("08MH001")
        & hydrology["parameter"].eq("discharge_unit_value"),
        ["timestamp_utc", "value"],
    ].copy()
    discharge = (
        discharge.set_index("timestamp_utc")["value"]
        .resample("1h")
        .mean()
        .rename("discharge_m3s")
        .reset_index()
    )
    flow_stages = hydrologic_stages.loc[
        hydrologic_stages["station_id"].eq("08MH001")
        & hydrologic_stages["parameter"].eq("discharge_unit_value")
        & hydrologic_stages["stage_id"].isin(["STAGE01", "STAGE02", "STAGE03"])
    ].set_index("stage_id")
    figure = go.Figure()
    figure.add_trace(go.Scatter(
        x=discharge["timestamp_utc"],
        y=discharge["discharge_m3s"],
        mode="lines",
        name="Chilliwack discharge · hourly mean",
        line={"color": "#0072B2", "width": 2.2},
        hovertemplate="<b>Regional gauge context</b><br>%{x|%d %b %Y %H:%M UTC}<br>Discharge: %{y:.1f} m³/s<extra></extra>",
    ))
    figure.add_trace(go.Scatter(
        x=dates,
        y=values,
        mode="lines+markers",
        name="RCM-derived EGS open-water flood class",
        line={"color": "#D55E00", "width": 3, "dash": "dot"},
        marker={"size": 10, "color": "#D55E00"},
        yaxis="y2",
        customdata=trajectory[["observation_id", "stage_label", "observation_role", "platform", "beam_mode", "source_resolution_m", "orbit_direction"]],
        hovertemplate="<b>%{customdata[0]}</b> · %{x|%d %b %Y %H:%M UTC}<br>Mapped EGS open-water flood class: %{y:.2f} ha<br>Regional context: %{customdata[1]}<br>Role: %{customdata[2]}<br>Platform / beam: %{customdata[3]} · %{customdata[4]}<br>Resolution / orbit: %{customdata[5]:.0f} m · %{customdata[6]}<extra></extra>",
    ))
    annotations = []
    stage_colors = {"STAGE01": "#D55E00", "STAGE02": "#7F8C8D", "STAGE03": "#009E73"}
    for stage_id in ("STAGE01", "STAGE02", "STAGE03"):
        if stage_id not in flow_stages.index:
            continue
        stage = flow_stages.loc[stage_id]
        figure.add_vline(x=stage["anchor_timestamp_utc"], line_dash="dash", line_width=1.2, line_color=stage_colors[stage_id])
        annotations.append({
            "x": stage["anchor_timestamp_utc"], "y": float(stage["value"]), "yref": "y",
            "text": f"{stage['stage_label']}<br>{float(stage['value']):.0f} m³/s",
            "showarrow": True, "arrowhead": 2, "ax": 0, "ay": -38,
        })
    annotations.extend([
        {"x": dates.iloc[0], "y": values.iloc[0], "yref": "y2", "text": "OBS01 · first available mapped frame", "showarrow": True, "arrowhead": 2, "ax": 35, "ay": -35},
        {"x": dates.iloc[-1], "y": values.iloc[-1], "yref": "y2", "text": "OBS07 · lower endpoint", "showarrow": True, "arrowhead": 2, "ax": 0, "ay": -34},
    ])
    figure.update_layout(
        height=520,
        margin={"l": 20, "r": 20, "t": 58, "b": 20},
        hovermode="x unified",
        dragmode=False,
        annotations=annotations,
        yaxis={"title": "Chilliwack discharge (m³/s)", "fixedrange": True, "rangemode": "tozero"},
        yaxis2={
            "title": "Mapped EGS open-water flood class (ha)", "fixedrange": True,
            "overlaying": "y", "side": "right", "range": [0, 70], "showgrid": False,
        },
        xaxis={"title": "UTC time", "fixedrange": True, "range": [pd.Timestamp("2025-12-07T00:00:00Z"), pd.Timestamp("2025-12-23T00:00:00Z")]},
        legend={"orientation": "h", "y": 1.10, "x": 0},
    )
    return figure


def render_monitor(acquisition: dict[str, Any]) -> None:
    trajectory = acquisition["trajectory"]
    render_header("Monitor", "How did regional hydrology and the seven discrete RCM-derived observations align from 7–22 December?")
    st.subheader("Regional hydrology and observed RCM response")
    st.plotly_chart(
        _monitor_figure(trajectory, acquisition["hydrology"], acquisition["hydrologic_stages"]),
        width="stretch",
        theme="streamlit",
        config={"displaylogo": False, "displayModeBar": False, "scrollZoom": False, "doubleClick": False, "responsive": True},
    )
    render_metric_rows([
        ("Fixed-reference total mapped water · OBS01", "1,026.80 ha", None),
        ("Fixed-reference total mapped water · OBS07", "993.52 ha", None),
        ("Gross recession from initial footprint", "35.44 ha", None),
    ])
    st.info("The blue gauge record corroborates two regional hydrologic pulses. The orange RCM-derived series begins with the first available mapped frame on 12 Dec and provides seven discrete spatial observations; it does not measure a continuous pixel-level hydrograph or the exact timing of either peak.")
    st.caption("The dotted line only connects observed acquisitions in order. It is not daily interpolation or a measured flood-peak estimate. The 35.44 ha gross recession is the portion of the OBS01 flood footprint absent at OBS07; the fixed-reference net endpoint decline is 33.28 ha. Different source resolutions, viewing geometry, radiometry, and changing water conditions contribute to non-monotonic intermediate values.")


def _direct_roads_table(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    roads = tables["roads"].loc[lambda frame: frame["direct_intersection"] & frame["name"].notna()].copy()
    roads["Road"] = roads["name"] + roads["ref"].fillna("").map(lambda value: f" / {value}" if value else "")
    return roads[["Road", "osm_id", "highway", "flood_intersection_m", "bridge"]].rename(
        columns={"osm_id": "OSM way", "highway": "Class", "flood_intersection_m": "Intersection (m)", "bridge": "Bridge tag"}
    )


def render_impact(tables: dict[str, pd.DataFrame], prepared: dict[str, Any]) -> None:
    render_header("Impact", "What assets or designated land could overlap the mapped water expansion?")
    render_metric_rows([
        ("Directly intersecting road ways", "14 ways", None),
        ("Direct road overlap", "0.346 km", None),
        ("Direct bridge-tagged way", "1 way", "Potential exposure only"),
        ("Mapped gain overlapping ALR designation", "36.65 ha", "66.7% of gain"),
    ])
    lens = st.segmented_control(
        "Impact lens",
        ["Infrastructure", "Agricultural land", "Community context"],
        default="Infrastructure",
        key="impact-lens",
        help="Choose the type of potential exposure to examine. This control changes the map narrative, not the scientific data.",
        width="stretch",
        wrap=True,
    ) or "Infrastructure"

    if lens == "Infrastructure":
        st.subheader("Infrastructure context")
        show_nearby = st.checkbox("Show roads within 250 m and the nearby Taylor Road bridge-tagged way", value=False, key="impact-nearby")
        layers = {"gain", "direct_roads", "direct_bridge"}
        if show_nearby:
            layers.update({"nearby_roads", "nearby_bridge"})
        render_map(prepared, "impact_infrastructure", "impact-infrastructure", active_layers=layers)
        st.caption("Grey lines are direct geometric intersections; teal highlights the bridge-tagged way. Neither overlap nor proximity confirms closure, damage, or flood depth.")
        st.dataframe(
            _direct_roads_table(tables),
            hide_index=True,
            width="stretch",
            column_config={
                "OSM way": st.column_config.NumberColumn(format="%d"),
                "Intersection (m)": st.column_config.NumberColumn(format="%.2f m"),
                "Road": st.column_config.TextColumn(width="large"),
            },
        )
        with st.expander("Bridge-tagged ways in the local context"):
            bridges = tables["bridges"].copy()
            bridges["Road"] = bridges["name"] + bridges["ref"].fillna("").map(lambda value: f" / {value}" if value else "")
            bridges["Relationship"] = bridges.apply(
                lambda row: f"{row.flood_intersection_m:.2f} m mapped intersection" if row.direct_intersection else f"{row.distance_to_gain_m:.0f} m from mapped gain",
                axis=1,
            )
            st.dataframe(bridges[["Road", "osm_id", "highway", "bridge", "Relationship"]].rename(columns={"osm_id": "OSM way", "highway": "Class", "bridge": "Bridge tag"}), hide_index=True, width="stretch")
    elif lens == "Agricultural land":
        st.subheader("Agricultural Land Reserve designation context")
        render_map(prepared, "impact_agriculture", "impact-agriculture")
        st.progress(0.667, text="66.7% of mapped flood gain overlaps ALR-designated land")
        st.info("ALR is a land designation, not a crop map. This mapped overlap does not demonstrate crop loss or agricultural damage.")
        st.caption("The blue layer is only the 36.65 ha portion of mapped gain that overlaps ALR designation; it is not the full ALR boundary.")
    else:
        st.subheader("Community geographic context")
        render_map(prepared, "impact_community", "impact-community")
        nearest = tables["communities"].sort_values("distance_to_gain_m").iloc[0]
        columns = st.columns(2)
        columns[0].metric("Nearest official place point", str(nearest["place_name"]))
        columns[1].metric("Distance to mapped gain", f"{nearest.distance_to_gain_m:.1f} m")
        st.write("The place point lies inside the study AOI. It provides geographic context only; the analysis does not estimate population exposure.")
        with st.expander("Other official place points"):
            nearby = tables["communities"].head(5)[["place_name", "inside_aoi", "distance_to_gain_m"]].rename(columns={"place_name": "Official place point", "inside_aoi": "Inside AOI", "distance_to_gain_m": "Distance (m)"})
            st.dataframe(nearby, hide_index=True, width="stretch", column_config={"Distance (m)": st.column_config.NumberColumn(format="%.1f m")})


def render_method_details() -> None:
    st.subheader("How the result was assessed")
    details = [
        ("Observation source", "Seven NRCan EGS RCM-derived flood products provide the local 12–21 Dec event sequence."),
        ("Semantic baseline and 20 m grid", "Open water is mapped outside a local semantic permanent-water baseline and compared on the fixed analytical grid."),
        ("Temporal comparison", "The dashboard reports observed near-event, recession, and recovery conditions without interpolating between acquisitions."),
        ("Independent recovery validation", "A Sentinel-2 recovery-period comparison supports interpretation while preserving its timing and sensor differences."),
        ("Exposure overlays and claim boundaries", "Roads, bridge-tagged ways, ALR designation, and place points provide context only; they do not establish damage, crop loss, or population impact."),
    ]
    for title, body in details:
        with st.expander(title):
            st.write(body)


def render_evidence(tables: dict[str, pd.DataFrame], manifest: dict[str, Any]) -> None:
    render_header("Evidence & Method", "Why should this result be trusted, and what are its limitations?")
    render_method_details()
    evidence = tables["evidence"].rename(columns={"evidence_type": "Evidence", "source": "Source", "date": "Date", "observation": "Observation", "role": "Role", "limitation": "Limitation"})
    st.subheader("Evidence chain")
    st.dataframe(evidence[["Evidence", "Date", "Observation", "Role"]], hide_index=True, width="stretch", column_config={"Observation": st.column_config.TextColumn(width="large"), "Role": st.column_config.TextColumn(width="medium")})
    with st.expander("Full provenance table"):
        st.dataframe(evidence, hide_index=True, width="stretch")
    st.subheader("Independent recovery-period comparison")
    render_metric_rows([(name, f"{value:.3f}", None) for name, value in VALIDATION_METRICS.items()])
    st.caption("The RCM and Sentinel-2 observations are approximately 6.2 days apart. Water recession, cloud masking, SAR/optical physics, spatial resolution, and mixed shoreline pixels contribute to disagreement; these are supportive, not perfect-agreement metrics.")
    with st.expander("Limitations and interpretation"):
        for limitation in tables["limitations"]["limitation"]:
            st.markdown(f"- {limitation}")
        st.markdown("- The mixed 5 m, 16 m, and 30 m EGS source resolutions are normalized to a 20 m analytical grid.")
        st.markdown("- The Folly Lake 5.88 pp value is empirical control-site context only, not a universal threshold.")
        st.markdown("- The case does not support climate-causation claims.")
    claim_left, claim_right = st.columns(2)
    with claim_left:
        with st.expander("Supported claims"):
            st.markdown("""- RCM-derived products map water expansion inside the AOI.
            - 54.92 ha of event-period water gain is mapped outside the semantic baseline.
            - The extent recedes toward the recovery observation.
            - Roads and ALR-designated land spatially overlap or lie near mapped gain.
            - The pattern is broadly consistent with official regional reporting.""")
    with claim_right:
        with st.expander("Restricted claims"):
            st.markdown("""- No confirmed road or bridge damage.
            - No flood-depth, population-impact, or crop-loss estimate.
            - No causal climate attribution.
            - No claim of complete Fraser Valley or infrastructure coverage.
            - The 5.88 pp context is not a universal threshold.""")
    st.subheader("Official sources")
    for row in tables["sources"].itertuples():
        st.markdown(f'<div class="source-card"><strong>{row.source}</strong> · {row.date}<br><span class="small-note">{row.documented_context}</span><br><a href="{row.url}" target="_blank">Open official source ↗</a></div>', unsafe_allow_html=True)
    st.caption(f"Handoff status: Phase {manifest['phase']} {manifest['status']} · Working CRS: {manifest['crs']}")


missing = [path for path in _expected_paths() if not path.is_file()]
if missing:
    st.error("The local Phase 5 handoff is incomplete. Restore the following files before starting the dashboard:")
    for path in missing:
        st.code(str(path.relative_to(BASE_DIR)))
    st.stop()

try:
    input_signature = _file_signature(_expected_paths())
    tables = load_tables(input_signature)
    vectors = load_vectors(input_signature)
    manifest = load_manifest(input_signature)
    acquisition_data = load_acquisition_data(input_signature)
    acquisition_data["trajectory"] = build_temporal_contract(acquisition_data)
    map_data = _decorate_map_data(vectors, tables)
except Exception as exc:
    st.error("The local Phase 4/5 handoff could not be loaded.")
    st.exception(exc)
    st.stop()

with st.sidebar:
    st.markdown("## 🛰️ Earth in Motion")
    st.caption("Lower Fraser flood case study")
    section = st.radio("Navigate", NAV_ITEMS)
    st.divider()
    st.markdown("**December 2025**  ")
    st.caption("36 km² study area · EPSG:32610")
    st.markdown('<span class="status-pill">Local data ready</span>', unsafe_allow_html=True)
    st.caption("No remote data requests at startup.")

if section == "Overview":
    render_overview(tables, map_data)
elif section == "Detect":
    render_detect(tables, map_data)
elif section == "Map":
    render_map_page(map_data, acquisition_data)
elif section == "Monitor":
    render_monitor(acquisition_data)
elif section == "Impact":
    render_impact(tables, map_data)
else:
    render_evidence(tables, manifest)

st.divider()
st.caption("Earth in Motion · Mission Accepted Space Hackathon 2026 · Potential exposure is not confirmed damage")
