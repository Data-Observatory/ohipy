## calculate_scores_s3.r
##
## Generates the R ohi-core reference scores for the s3_2026.v01 comparative scenario,
## writing tests/comparative/fixtures/s3_2026.v01/baseline.csv. Run inside the ohicore-r-env
## Docker image (repo mounted at /home/project). Only used by the gated regeneration path
## (tests/parity/s3_fixture.regenerate); the default test path compares against the committed
## baseline.csv. Modeled on tests/comparative/calculate_scores.r (native Conf/Layers/CalculateAll).

## load ohicore + goal-model libraries (only if not already loaded)
if (!"ohicore" %in% (.packages())) {
  suppressWarnings(require(ohicore))
  library(tidyr)
  library(plyr)     # attach BEFORE dplyr so dplyr masks plyr's mutate/arrange/summarise;
  library(dplyr)    # plyr still provides ddply/.() used by the ICO goal model
  library(stringr)
}

## shared conf lives in the pinned chl checkout (config.R + functions.R + matrices)
setwd("/home/project/chl/comunas")
conf <- ohicore::Conf("conf")

## R reads the chl-schema s3_2026.v01 layers via chl's OWN registry (species column
## named 'especie'/'spp' etc.) — mirrors tests/comparative/calculate_scores.r. ohipy reads
## the ohipy-native layers separately (see tests/parity/s3_fixture.py).
layers_dir <- "/home/project/tests/comparative/scenarios/s3_2026.v01/layers/csv"
registry <- "layers.csv"  # relative to chl/comunas -> chl's own registry

ohicore::CheckLayers(registry, layers_dir, flds_id = conf$config$layers_id_fields)
layers <- ohicore::Layers(registry, layers_dir)

## scenario_year is read as a scalar by the goal models; it is not a registered layer
layers$data$scenario_year <- 2024

scores <- ohicore::CalculateAll(conf, layers)

write.csv(
  scores,
  "/home/project/tests/comparative/fixtures/s3_2026.v01/baseline.csv",
  na = "", row.names = FALSE
)
