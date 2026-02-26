# Issues Found

## 2026-02-26: Weights normalization bug in ConfigOverlay

**Location:** `src/ohipy/config_overlay.py` - `apply_weights()` method

**Problem:** 
The `apply_weights()` method normalizes ALL weights globally to sum to 1, instead of normalizing within parent groups.

**Expected behavior:**
- Weights should be normalized within each parent group (FP, LE, SP, BD)
- Example: FIS and MAR are children of FP, their weights should sum to 1 within FP only

**Current behavior:**
```python
# Default weights
FIS=0.5, MAR=0.5 (correct, sum to 1 within FP)

# After override FIS=0.8, MAR=0.2
# ALL 18 goals normalized to sum to 1
FIS becomes ~0.057, MAR becomes ~0.014 (incorrect!)
```

**Impact:**
**Status:** ✅ FIXED on 2026-02-26

**Fix:** Modified `apply_weights()` to normalize:
1. Supragoals (no parent) among themselves to sum to 1
2. Subgoals within each parent group to sum to 1
