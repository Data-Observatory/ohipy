# GOALS DIRECTORY

**Directory:** `src/ohipy/goals/`

## OVERVIEW

18 goal calculation functions (14 pre-index, 4 post-index) computing status and trend scores for ocean health dimensions.

## WHERE TO LOOK

| File | Goal | Lines | Type | Notes |
|------|------|-------|------|-------|
| fis.py | FIS | 187 | pre-index | Fisheries |
| mar.py | MAR | ~130 | pre-index | Mariculture |
| fp.py | FP | | post-index | FIS + MAR weighted |
| ao.py | AO | ~100 | pre-index | Artisanal Opportunity |
| np.py | NP | ~160 | pre-index | Natural Products |
| cs.py | CS | ~100 | pre-index | Carbon Storage |
| cp.py | CP | ~100 | pre-index | Coastal Protection |
| tr.py | TR | ~100 | pre-index | Tourism |
| liv.py | LIV | 203 | pre-index | Livelihoods |
| eco.py | ECO | ~100 | pre-index | Economy |
| le.py | LE | | post-index | LIV + ECO weighted |
| ico.py | ICO | ~80 | pre-index | Iconic Species |
| lsp.py | LSP | ~80 | pre-index | Lasting Special Places |
| sp.py | SP | | post-index | ICO + LSP equal weight |
| cw.py | CW | 262 | pre-index | Clean Water, has R bug |
| hab.py | HAB | ~100 | pre-index | Habitats |
| spp.py | SPP | ~80 | pre-index | Species |
| bd.py | BD | | post-index | HAB + SPP equal weight |

## GOAL TYPES

### Pre-index (14 goals)
- Called in Step 2 of calculate_all()
- Signature: `def GOAL(layers: dict) -> tuple[pl.DataFrame, pl.DataFrame]`
- Returns: `(status_df, trend_df)`
- status_df columns: `[region_id, score, dimension="status"]`
- trend_df columns: `[region_id, score, dimension="trend"]`
- Score scaled 0-100 before return

Goals: FIS, MAR, AO, NP, CS, CP, TR, LIV, ECO, ICO, LSP, CW, HAB, SPP

### Post-index (4 goals)
- Called in Step 6 of calculate_all()
- Receive full scores DataFrame, return updated scores
- Signature VARIES by goal:
  - `LE(scores, layers) -> pl.DataFrame`
  - `FP(layers, scores) -> pl.DataFrame`
  - `SP(layers, scores) -> pl.DataFrame`
  - `BD(layers, scores) -> pl.DataFrame`

Goals: LE, FP, SP, BD

## CRITICAL PATTERNS

1. **R source reference**: Every file has comment referencing R lines in `ohi-science-chl/comunas/conf/functions.R`

2. **NaN handling**: Must match R `mean()` behavior (NA if any value is NA). Use `is_finite()`, not `isnan()`

3. **R parity**: Calculation order, rounding (`.round(4)`), and NaN handling must match R exactly

4. **cw.py R bug**: Lines 211-233 deliberately replicate R bug using pres_data1 (STATUS) instead of trend_data1 (TREND). Do NOT fix without team approval

5. **Layers dict**: `layers["data"]` is `{layer_name: polars.DataFrame}`, `layers["meta"]` is polars DataFrame

## ANTI-PATTERNS

- DO NOT change calculation logic without checking corresponding R source lines
- DO NOT use different rounding than R
- DO NOT fix cw.py R bug replication
- DO NOT change function signatures (pre-index vs post-index differ intentionally)
