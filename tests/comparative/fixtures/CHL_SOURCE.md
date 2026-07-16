# chl-derived fixtures (dimension_removal/, noise_*pct/, original/)

- **Source**: `chl` git submodule (`OHI-Science/chl` upstream, pinned in this repo's
  `.gitmodules`), Chile "comunas" OHI assessment.
- **Submodule commit used to generate these fixtures**: `fe99df553bfa8da025b6ecee1a80ef6d802a3a63`.
- **Regenerate**: bump the submodule SHA and regenerate these fixtures together in the same
  commit (`OHI_AUTO_GENERATE_FIXTURES=1`, via `tests/parity/setup_fixtures.py` /
  `tests/parity/dimension_removal_fixtures.py`), so the (data, fixture, code) triple never
  drifts apart — see the branch-cleanup discussion for why floating to submodule HEAD without
  a pinned commit breaks parity-test reproducibility.
