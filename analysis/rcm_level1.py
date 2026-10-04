"""Discovery, metadata parsing, and vendor checksum verification for RCM L1 GRD.

This module only reads metadata and hashes. It does not open the large imagery
unless a caller explicitly asks rasterio to do so.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


PILOT = {
    "P01": ("2025-12-14T14:24:21Z", "16M9", "stripmap16_desc", "OBS02"),
    "P02": ("2025-12-15T01:50:36Z", "SC30MB", "scansar30_asc", "OBS03"),
    "P03": ("2025-12-17T14:16:34Z", "16M16", "stripmap16_desc", "OBS05"),
    "P04": ("2025-12-19T01:50:11Z", "SC30MB", "scansar30_asc", "OBS06"),
    "P05": ("2025-12-21T14:16:46Z", "16M16", "stripmap16_desc", "OBS07"),
}


def _tag(node: ET.Element) -> str:
    return node.tag.rsplit("}", 1)[-1]


def _text(root: ET.Element, *names: str, default: str | None = None) -> str | None:
    wanted = set(names)
    for node in root.iter():
        if _tag(node) in wanted and node.text and node.text.strip():
            return node.text.strip()
    return default


def _numbers(root: ET.Element, *names: str) -> list[float]:
    wanted = set(names)
    out: list[float] = []
    for node in root.iter():
        if _tag(node) in wanted and node.text:
            out.extend(float(x) for x in re.findall(r"[-+]?\d+(?:\.\d+)?(?:[Ee][-+]?\d+)?", node.text))
    return out


def _float(root: ET.Element, *names: str) -> float | None:
    value = _text(root, *names)
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _find(root: Path, filename: str) -> Path | None:
    matches = list(root.rglob(filename))
    return matches[0] if matches else None


def _mode_group(mnemonic: str, direction: str) -> str:
    if mnemonic.startswith("16M") and direction.lower().startswith("desc"):
        return "stripmap16_desc"
    if mnemonic.startswith("SC30") and direction.lower().startswith("asc"):
        return "scansar30_asc"
    if mnemonic.startswith("SC30"):
        return "scansar30"
    return "unknown"


def _product_root(product_xml: Path) -> Path:
    # The input is normally .../<download>/<product>/metadata/product.xml.
    # Keep the product directory, not the download container, as the source.
    return product_xml.parent.parent


def _incidence_bounds(product_root: Path) -> tuple[float | None, float | None]:
    path = _find(product_root, "incidenceAngles.xml")
    if not path:
        return None, None
    try:
        values = _numbers(ET.parse(path).getroot(), "incidenceAngle", "angle", "angles")
    except (ET.ParseError, OSError, ValueError):
        return None, None
    return (min(values), max(values)) if values else (None, None)


@dataclass(frozen=True)
class Level1Product:
    observation_id: str
    timestamp_utc: str
    platform: str
    product_id: str
    beam_mode: str
    mode_group: str
    nominal_resolution_m: float | None
    sampled_pixel_spacing_m: float | None
    orbit_direction: str
    relative_orbit: str | None
    polarizations: str
    incidence_min_deg: float | None
    incidence_max_deg: float | None
    source_product: str
    product_xml: str
    hashfile: str | None
    product_format: str | None
    input_bytes: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_product(product_xml: Path, observation_id: str) -> Level1Product:
    root = ET.parse(product_xml).getroot()
    inner_root = _product_root(product_xml)
    # EODMS downloads commonly wrap the SAFE-like product in an outer folder;
    # the vendor hashfile lives beside that inner product directory.
    product_root = inner_root.parent if (inner_root.parent / "hashfile").exists() else inner_root
    mnemonic = _text(root, "beamModeMnemonic", default="") or ""
    beam = _text(root, "beamMode", default="") or ""
    direction = _text(root, "passDirection", "orbitDirection", default="unknown") or "unknown"
    timestamp = _text(root, "rawDataStartTime", "acquisitionStartTime", default="") or ""
    timestamp = timestamp.replace("+00:00", "Z")
    product_id = _text(root, "productId", "productID", default=product_root.name) or product_root.name
    platform = _text(root, "satellite", "platform", default="RCM") or "RCM"
    pols = _text(root, "polarizations", default="") or ""
    if not pols:
        pols = "/".join(sorted(p.name for p in product_root.glob("measurement/*") if p.is_dir()))
    incidence_min, incidence_max = _incidence_bounds(inner_root)
    nominal_resolution = _float(root, "nominalResolution", "resolution")
    if nominal_resolution is None:
        nominal_resolution = 30.0 if mnemonic.startswith("SC30") else (16.0 if mnemonic.startswith("16M") else None)
    return Level1Product(
        observation_id=observation_id,
        timestamp_utc=timestamp,
        platform=platform,
        product_id=product_id,
        beam_mode=mnemonic or beam,
        mode_group=_mode_group(mnemonic, direction),
        nominal_resolution_m=nominal_resolution,
        sampled_pixel_spacing_m=_float(root, "sampledPixelSpacing"),
        orbit_direction=direction,
        relative_orbit=_text(root, "relativeOrbit", "relativeOrbitNumber"),
        polarizations=pols,
        incidence_min_deg=incidence_min,
        incidence_max_deg=incidence_max,
        source_product=str(product_root),
        product_xml=str(product_xml),
        hashfile=str(_find(product_root, "hashfile")) if _find(product_root, "hashfile") else None,
        product_format=_text(root, "productType", "productFormat"),
        input_bytes=sum(p.stat().st_size for p in product_root.rglob("*") if p.is_file()),
    )


def _candidate_product_xml(root: Path) -> Iterable[Path]:
    yield from sorted(root.rglob("metadata/product.xml"))


def discover_products(root: str | Path) -> pd.DataFrame:
    """Discover every local RCM product and return the stable inventory schema."""
    root = Path(root)
    rows = []
    for index, product_xml in enumerate(_candidate_product_xml(root), start=1):
        product_root = _product_root(product_xml)
        # Use the actual acquisition timestamp for deterministic IDs when possible.
        try:
            parsed = _parse_product(product_xml, f"L1_{index:02d}")
            obs = pd.Timestamp(parsed.timestamp_utc).strftime("%Y%m%dT%H%M%SZ")
            parsed = Level1Product(obs, *list(parsed.as_dict().values())[1:])
        except Exception:
            parsed = _parse_product(product_xml, f"L1_{index:02d}")
        rows.append(parsed.as_dict())
    columns = list(Level1Product.__dataclass_fields__)
    return pd.DataFrame(rows, columns=columns).sort_values("timestamp_utc").reset_index(drop=True)


def _hash_entries(hashfile: Path) -> list[tuple[str, str]]:
    entries = []
    for line in hashfile.read_text(errors="replace").splitlines():
        match = re.search(r"\b([0-9a-fA-F]{40})\b\s+[* ]?(.+?)\s*$", line)
        if match:
            entries.append((match.group(2).strip(), match.group(1).lower()))
    return entries


def verify_product(product: str | Path | Level1Product) -> dict[str, Any]:
    """Verify a product hashfile and report missing/mismatched files."""
    product_root = Path(product.source_product if isinstance(product, Level1Product) else product)
    hashfile = _find(product_root, "hashfile")
    if not hashfile:
        return {"product": str(product_root), "status": "missing_hashfile", "missing": [], "mismatched": []}
    missing, mismatched = [], []
    for relative, expected in _hash_entries(hashfile):
        relative_path = Path(relative)
        path = product_root.parent / relative_path if relative_path.parts and relative_path.parts[0] == product_root.name else product_root / relative_path
        if not path.exists():
            missing.append(relative)
            continue
        digest_builder = hashlib.sha1()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest_builder.update(chunk)
        digest = digest_builder.hexdigest()
        if digest != expected:
            mismatched.append(relative)
    normalized_hashfile = "\n".join(line.strip() for line in hashfile.read_text(errors="replace").splitlines() if line.strip())
    return {
        "product": str(product_root),
        "status": "ok" if not missing and not mismatched else "failed",
        "missing": missing,
        "mismatched": mismatched,
        # Hash the normalized manifest text so line-ending differences do not
        # change provenance while the listed SHA-1 values remain untouched.
        "input_product_hash": hashlib.sha256(normalized_hashfile.encode()).hexdigest(),
        "entries": len(_hash_entries(hashfile)),
    }


def pilot_inventory(inventory: pd.DataFrame) -> pd.DataFrame:
    """Select the five registered pilot timestamps without changing inventory."""
    timestamps = {pd.Timestamp(item[0], tz="UTC").floor("s") for item in PILOT.values()}
    values = pd.to_datetime(inventory["timestamp_utc"], utc=True).dt.floor("s")
    return inventory.loc[values.isin(timestamps)].copy().reset_index(drop=True)
