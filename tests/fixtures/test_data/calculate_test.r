## calculate_test.R
## Test calculation script for OHI Python validation
## This script uses the test_data directory instead of chl/comunas
## Run from project root: docker run --rm -v "$PWD":/home/project -w /home/project ohicore-r-env Rscript tests/fixtures/test_data/calculate_test.r

## Remember the original working directory so we can restore it
owd <- getwd()

## Set working directory to the test_data scenario
scenario_dir <- file.path("tests", "fixtures", "test_data")
setwd(scenario_dir)

## Create output directory if it doesn't exist
output_dir <- file.path(owd, "tests", "output")
if (!dir.exists(output_dir)) {
  dir.create(output_dir, recursive = TRUE)
}

## Load ohicore and libraries used in goal models (only if not already loaded)
if (!"ohicore" %in% (.packages())) {
  suppressWarnings(require(ohicore))
  library(tidyr)    # install.packages('tidyr')
  library(dplyr)    # install.packages('dplyr')
  library(plyr)
  library(stringr)  # install.packages('stringr')
}

## Load scenario configuration
conf <- ohicore::Conf("conf")

## Check that scenario layers files in the layers folder match layers.csv registration
## Layers files are not modified.
ohicore::CheckLayers("layers.csv", "layers", flds_id = conf$config$layers_id_fields)

## Load scenario layers for ohicore to access
layers <- ohicore::Layers("layers.csv", "layers")
layers$data$scenario_year <- 2024

## Calculate scenario scores
scores <- ohicore::CalculateAll(conf, layers)

## Restore original working directory
setwd(owd)

## Save scores to tests/output directory
write.csv(scores, file.path("tests", "output", "scores_r_test.csv"), na = "NA", row.names = FALSE)

cat("Scores written to: tests/output/scores_r_test.csv\n")
