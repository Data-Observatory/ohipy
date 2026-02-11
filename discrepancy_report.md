# Index Discrepancy Root Cause Report

## Summary

The Index discrepancy was caused by a **post-index function in the Chile assessment (functions.R)** that **duplicates the LE and FP rows in the scores table** before Index aggregation. This duplication changes the effective weight of FP and LE in the `weighted.mean()` used to compute Index score and future in `ohicore::CalculateAll()`, even though `goals.csv` weights are equal for all supragoals.

There are **no hardcoded Index weights in ohicore**. The discrepancy is caused by **duplicate rows** feeding the Index aggregation.

---

## Where the Discrepancy Happens (R)

### 1) FP post-index function duplicates rows

**File:** `ohi-science-chl/comunas/conf/functions.R`  
**Function:** `FP`  
**Lines:** 259–294  

Key lines (exact in file):

```r
s<- s  %>%
  dplyr::group_by(region_id, dimension) %>%
  dplyr::summarize(score = weighted.mean(score, weight, na.rm = TRUE)) %>%
  dplyr::mutate(goal = "FP") %>%
  dplyr::ungroup() %>%
  dplyr::select(region_id, goal, dimension, score) %>%
  data.frame()

scores<- rbind(scores, s)

# return all scores
return(rbind(scores, s))
```

**Effect:** `s` is appended to `scores`, then `return(rbind(scores, s))` appends `s` **again**, duplicating FP rows.

---

### 2) LE post-index function duplicates existing scores

**File:** `ohi-science-chl/comunas/conf/functions.R`  
**Function:** `LE`  
**Lines:** 951–971  

Key lines (exact in file):

```r
s <- scores %>%
  dplyr::filter(goal %in% c('LIV', 'ECO'),
                dimension %in% c('status', 'trend', 'future', 'score')) %>%
  dplyr::group_by(region_id, dimension) %>%
  dplyr::summarize(score = mean(score, na.rm = TRUE)) %>%
  dplyr::ungroup() %>%
  dplyr::arrange(region_id) %>%
  dplyr::mutate(goal = "LE") %>%
  dplyr::select(region_id, goal, dimension, score) %>%
  data.frame()

s<- rbind(scores, s)

# return scores
return(rbind(scores, s))
```

**Effect:** `scores` is duplicated entirely when `rbind(scores, s)` is returned, which effectively **duplicates all existing rows**, not just LE.

---

## Why This Changes Index Weights

Index is computed in **ohicore** by:

**File:** `ohicore/R/CalculateAll.R`  
**Lines:** 189–204  

```r
dplyr::filter(dimension=='score', goal %in% supragoals) %>%
merge(conf$goals %>% dplyr::select(goal, weight)) %>%
dplyr::group_by(region_id) %>%
dplyr::summarise(score = weighted.mean(score, weight, na.rm=T))
```

Because the **scores table contains duplicate FP and LE rows**, the **effective weight of FP/LE is higher**, even though all supragoal weights are `1.0` in `goals.csv`.

---

## Evidence the Weights in R Are Not Hardcoded

**File:** `ohi-science-chl/comunas/conf/goals.csv`  
All supragoals (FP, AO, NP, CS, CP, TR, LE, SP, CW, BD) have **weight = 1**.

Thus, **R does not hardcode special Index weights**. The discrepancy originates from **duplicate rows** in post-index functions.

---

## Python Replication (Root-Cause Match)

To match R **without hardcoded multipliers**, the Python translation must replicate the duplicate-row behavior in these post-index functions:

**FP (python/ohi/goals/fp.py)**
```python
scores_updated = pd.concat([scores, fp_scores, fp_scores], ignore_index=True)
```

**LE (python/ohi/goals/le.py)**
```python
scores_updated = pd.concat([scores, scores, le_scores], ignore_index=True)
```

These changes reproduce the R duplication and yield the same Index values **while keeping `goals.csv` weights intact**.

---

## Conclusion

The root cause of the Index mismatch is **not** in `goals.csv` or `ohicore` Index logic. It is a **data duplication side-effect** in the Chile assessment's post-index functions (`FP` and `LE`) that **changes the effective weights** used by `CalculateAll()`.

This is the only verified cause, and Python now matches R **without hardcoding weights** by replicating the same duplication behavior.
