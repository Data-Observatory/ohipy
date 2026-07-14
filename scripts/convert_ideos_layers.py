#!/usr/bin/env python3
"""Convert IDEOS parquet layers into the chl/comunas OHI-core CSV layers.

Reads the parquet layers exported by proj-IDEOS-metas, selects the 2024
assessment data, renames columns to the OHI-core conventions used by the R
toolbox, and writes a parallel, non-destructive scenario under
``chl/comunas/layers_ideos/`` (nothing in ``chl/comunas/layers/`` is touched).

See the approved plan for the full rationale. Key rule for the year dimension
(target-schema-driven):

* Target CSV has **no** ``year`` column  -> reduce to one row per key using the
  2024 value (fallback: latest <= 2024).
* Target CSV **has** ``year``            -> if the ``ohi_year==2024`` slice spans
  more than one data year, keep that slice (genuine scenario replicate);
  otherwise keep a 5-year window (2020..2024) of the full history so the goal
  models can compute status + trend.
* Static layers (``ohi_year`` all null, no ``year``) -> keep every row.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

SCEN_YEAR = 2024
WINDOW = list(range(SCEN_YEAR - 4, SCEN_YEAR + 1))  # 2020..2024

REPO = Path(__file__).resolve().parents[1]
PARQUET_DIR = REPO.parent / "proj-IDEOS-metas" / "data" / "layers"
LAYERS_CSV = REPO / "chl" / "comunas" / "layers.csv"
SRC_LAYERS = REPO / "chl" / "comunas" / "layers"
OUT_DIR = REPO / "chl" / "comunas" / "layers_ideos"

# layer name -> parquet stem, when it differs from the layer name
PARQUET_OVERRIDE = {
    "np_harvest_tonnes_weigth": "np_harvest_tonnes_weight",  # registry misspelling
}

# layer -> {parquet_column: target_column}. cut_com->rgn_id is applied globally.
RENAME_OVERRIDE = {
    "fis_meancatch": {"vernacular_name": "Spp"},
    "fis_b_bmsy": {"vernacular_name": "Especie"},
    "mar_harvest_tonnes": {"species_type": "especie"},
    "mar_sustainability_scores": {"species_type": "especie", "coef": "coeff"},
    "ico_status": {"scientific_name": "specie"},
    "ico_trend": {"scientific_name": "specie"},
    "rgn_area": {"comuna": "rgn_name"},
    "lsp_area_inland1mn": {"lsp_porc": "value_1"},
    "lsp_area_offshore3mn": {"lsp_porc": "value_3"},
    "hab_extension": {"area_km2": "value"},
    "hab_pref": {"punto_referencia": "pref"},
    "cs_habitat_pref": {"punto_referencia": "pref"},
}

# goal models that reference data years earlier than the standard 5-yr window
WIDE_WINDOW = {"hab_extension": list(range(2018, SCEN_YEAR + 1))}  # HAB uses 2018:2022


def parquet_path(layer: str) -> Path | None:
    stem = PARQUET_OVERRIDE.get(layer, layer)
    for cand in (stem, layer):
        p = PARQUET_DIR / f"{cand}.parquet"
        if p.exists():
            return p
    return None


def target_header(filename: str) -> list[str] | None:
    p = SRC_LAYERS / filename
    if not p.exists():
        return None
    return pd.read_csv(p, nrows=0).columns.tolist()


def reshape(df: pd.DataFrame, layer: str) -> pd.DataFrame:
    """Rename to target column names and cast ids; KEEP ohi_year / year for selection."""
    df = df.copy()
    # region key: prefer cut_com (padded string) -> rgn_id (int); drop redundant int rgn_id
    if "cut_com" in df.columns:
        if "rgn_id" in df.columns:
            df = df.drop(columns=["rgn_id"])
        df = df.rename(columns={"cut_com": "rgn_id"})
    if "rgn_id" in df.columns:
        df["rgn_id"] = pd.to_numeric(df["rgn_id"], errors="coerce").astype("Int64")
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    for src, dst in RENAME_OVERRIDE.get(layer, {}).items():
        if src in df.columns:
            df = df.rename(columns={src: dst})
    return df


def select_rows(df: pd.DataFrame, layer: str, tgt: list[str], value_col: str,
                existing_nyears: int | None) -> pd.DataFrame:
    """Choose the rows for the 2024 scenario. `df` is already reshaped (target names).

    `existing_nyears` is the distinct-year count of the existing target CSV; it is the
    ground truth for how many years the goal model expects. Some layers carry a `year`
    column but are single-year snapshots at scen_year (ao_scores, ao_trend, cw_*_trend) --
    the goal models read them without filtering year, so emitting a multi-year series
    would create duplicate (region, dimension) rows.
    """
    has_oy = "ohi_year" in df.columns and df["ohi_year"].notna().any()
    base = df[df["ohi_year"] == SCEN_YEAR] if has_oy else df
    tgt_has_year = "year" in tgt

    if tgt_has_year:
        if existing_nyears == 1:
            # single-year snapshot at scen_year: one value per key
            sel = base[base["year"] == SCEN_YEAR] if "year" in base.columns else base
        else:
            n_years = base["year"].dropna().nunique() if "year" in base.columns else 0
            if n_years > 1:
                sel = base  # genuine scenario replicate: keep the 2024 slice
            elif "year" in df.columns:
                window = WIDE_WINDOW.get(layer, WINDOW)
                sel = df[df["year"].isin(window)]  # snapshot: keep the multi-year window
            else:
                sel = base
    else:
        # single value per key: reduce only if the slice actually duplicates keys
        key = [c for c in tgt if c != value_col and c in base.columns]
        if "year" in base.columns and key and base.duplicated(subset=key).any():
            b = base.copy()
            b["__p"] = (b["year"] == SCEN_YEAR).astype(int)  # prefer 2024, else latest
            b = b.sort_values(["__p", "year"]).drop_duplicates(subset=key, keep="last")
            sel = b.drop(columns="__p")
        else:
            sel = base

    drop = [c for c in ["ohi_year"] if c in sel.columns]
    if "year" in sel.columns and "year" not in tgt:
        drop.append("year")
    return sel.drop(columns=drop)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    meta = pd.read_csv(LAYERS_CSV)

    regions: set[int] = set()  # filled once rgn_area is processed
    rows = []
    fallbacks = []
    warnings = []

    # process rgn_area first so we know the region master for validation
    order = sorted(meta.index, key=lambda i: meta.loc[i, "layer"] != "rgn_area")

    for idx in order:
        r = meta.loc[idx]
        layer, filename = r["layer"], r["filename"]
        if not isinstance(filename, str):
            continue
        out_path = OUT_DIR / filename
        src_path = SRC_LAYERS / filename

        pq = parquet_path(layer)
        if pq is None:
            if src_path.exists():
                shutil.copyfile(src_path, out_path)
                fallbacks.append((layer, "no parquet -> copied existing"))
            else:
                warnings.append((layer, "no parquet and no existing CSV"))
            continue

        tgt = target_header(filename)
        if tgt is None:
            tgt = [c for c in ["rgn_id", r.get("fld_category"), r.get("fld_year"),
                               r.get("fld_value")] if isinstance(c, str) and c]

        # year cardinality of the existing CSV = ground truth for how many years to emit
        existing_nyears = None
        if src_path.exists():
            _old = pd.read_csv(src_path)
            if "year" in _old.columns:
                existing_nyears = _old["year"].dropna().nunique()

        df = pd.read_parquet(pq)
        df = reshape(df, layer)
        df = select_rows(df, layer, tgt, value_col=r["fld_value"], existing_nyears=existing_nyears)

        missing = [c for c in tgt if c not in df.columns]
        if missing:
            if src_path.exists():
                shutil.copyfile(src_path, out_path)
                fallbacks.append((layer, f"parquet missing {missing} -> copied existing"))
            else:
                warnings.append((layer, f"parquet missing {missing}, no existing CSV"))
            continue

        out = df[tgt].copy()

        # dedupe safety on key columns (id + category + year that the target keeps)
        key_cols = [c for c in tgt if c != r["fld_value"]] or tgt
        ndup = int(out.duplicated(subset=key_cols).sum())
        if ndup:
            warnings.append((layer, f"{ndup} duplicate key rows on {key_cols}"))

        out.to_csv(out_path, index=False)

        if layer == "rgn_area" and "rgn_id" in out.columns:
            regions = set(int(x) for x in out["rgn_id"].dropna().unique())

        # validation vs existing CSV
        note = ""
        new_rgns = set(int(x) for x in out["rgn_id"].dropna().unique()) if "rgn_id" in out.columns else set()
        if src_path.exists():
            old = pd.read_csv(src_path)
            if list(old.columns) != tgt:
                note = f"HEADER DIFF old={list(old.columns)}"
            if "rgn_id" in old.columns:
                old_n = old["rgn_id"].nunique()
                if abs(len(new_rgns) - old_n) > 10:
                    note = (note + " " if note else "") + f"RGN COUNT new={len(new_rgns)} old={old_n}"
        yr_span = ""
        if "year" in out.columns and out["year"].notna().any():
            yr_span = f"{int(out['year'].min())}-{int(out['year'].max())}"
        orphans = ""
        if regions and new_rgns:
            oo = sorted(new_rgns - regions)
            if oo:
                orphans = f"orphan_rgns={oo}"
        rows.append((layer, len(out), yr_span, ndup, note, orphans))

    # ---- summary ----
    print(f"\nWrote {len(rows)} converted layers to {OUT_DIR}")
    print(f"{'layer':<34}{'rows':>7}{'years':>12}{'dup':>5}  notes")
    for layer, n, span, dup, note, orphan in sorted(rows):
        flag = " ".join(x for x in (note, orphan) if x)
        print(f"{layer:<34}{n:>7}{span:>12}{dup:>5}  {flag}")
    if fallbacks:
        print("\nFallbacks (copied existing CSV):")
        for layer, why in fallbacks:
            print(f"  {layer:<34} {why}")
    if warnings:
        print("\n*** WARNINGS ***")
        for layer, why in warnings:
            print(f"  {layer:<34} {why}")
    print(f"\nregion master (rgn_area): {len(regions)} regions")
    return 0


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parquet-dir", type=Path, default=PARQUET_DIR,
                    help="Directory of source *.parquet layers "
                         f"(default: {PARQUET_DIR})")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR,
                    help=f"Output directory for the CSV layers (default: {OUT_DIR})")
    _a = ap.parse_args()
    # override the module globals the functions read (defaults keep old behaviour)
    PARQUET_DIR = _a.parquet_dir
    OUT_DIR = _a.out_dir
    raise SystemExit(main())
