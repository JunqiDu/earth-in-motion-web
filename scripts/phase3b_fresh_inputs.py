#!/usr/bin/env python
"""Fetch only three small official FWA windows for the frozen spatial holdout.

No satellite downloads, EGS performance reads, or training-label updates.
Existing snapshots are not overwritten. This command never runs at app startup.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.physical_constraints import sha256_file

SERVICE = "https://delivery.maps.gov.bc.ca/arcgis/rest/services/whse/bcgw_pub_whse_basemapping/MapServer"
OUT = ROOT / "data/processed/phase3b/rf_v2_final/sources/fresh_neighbor"
LAYERS = {"streams": 34, "rivers": 17, "lakes": 20}
BOUNDS = (570110, 5444740, 571430, 5447740)


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    # A fixed 90m context margin supports a 60m distance policy at AOI edges.
    envelope = (BOUNDS[0] - 90, BOUNDS[1] - 90, BOUNDS[2] + 90, BOUNDS[3] + 90)
    for name, layer in LAYERS.items():
        path = OUT / (name + ".geojson")
        params = {"where": "1=1", "geometry": ",".join(map(str, envelope)),
                  "geometryType": "esriGeometryEnvelope", "inSR": "32610", "outSR": "32610",
                  "spatialRel": "esriSpatialRelIntersects", "outFields": "OBJECTID",
                  "returnGeometry": "true", "f": "geojson"}
        url = f"{SERVICE}/{layer}/query?{urlencode(params)}"
        if not path.exists():
            with urlopen(url, timeout=60) as response:
                data = json.loads(response.read())
            if "error" in data or "features" not in data or data.get("exceededTransferLimit"):
                raise RuntimeError(f"Incomplete FWA response: {name}")
            # Store a minimal fixed-context extract, not whole returned waterbodies.
            from shapely.geometry import shape, mapping, box
            features = []
            for feature in data["features"]:
                geometry = shape(feature["geometry"]).intersection(box(*envelope))
                if not geometry.is_empty:
                    features.append({"type": "Feature", "properties": feature.get("properties", {}), "geometry": mapping(geometry)})
            data = {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "EPSG:32610"}}, "features": features}
            path.write_text(json.dumps(data))
        data = json.loads(path.read_text())
        records.append({"dataset": "BC Freshwater Atlas", "layer": name, "layer_id": layer,
                        "source_url": url, "access_utc": datetime.now(timezone.utc).isoformat(),
                        "path": str(path.relative_to(ROOT)), "sha256": sha256_file(path),
                        "feature_count": len(data["features"]), "request_bounds": envelope,
                        "crs": "EPSG:32610", "role": "independent hydro proximity only, no EGS training"})
        print(name, len(data["features"]), path.stat().st_size, flush=True)
    provenance = OUT / "provenance.json"
    if not provenance.exists():
        provenance.write_text(json.dumps({"aoi": BOUNDS, "margin_m": 90, "sources": records}, indent=2))


if __name__ == "__main__":
    run()
