## calculate_scores.R
# WARNING: Run this from the root of the project.

## calculate_scores.R ensures all files are properly configured and calculates OHI scores.
## - configure_toolbox.r ensures your files are properly configured. It is a script in your repository.
## - CalculateAll() calculates OHI scores. It is a function in the `ohicore` R package
##   (this can be written in R as `ohicore::CalculateAll()`).

## When you begin, configure_toolbox.r and CalculateAll() will calculate scores using
## the 'templated' data and goal models provided. We suggest you work
## goal-by-goal as you prepare data in the prep folder and develop goal models
## in functions.r. Running configure_toolbox.r and a specific goal model line-by-line
## in functions.R is a good workflow.

## configure toolbox and calculate scores using paths relative to the project root

## remember the original working directory so we can restore it
owd <- getwd()

## set working directory to the comunas scenario that contains conf and layers
scenario_dir <- file.path("chl", "comunas")
setwd(scenario_dir)

## load ohicore and libraries used in goal models (only if not already loaded)
if (!"ohicore" %in% (.packages())) {
  suppressWarnings(require(ohicore))
  library(tidyr)    # install.packages('tidyr')
  library(dplyr)    # install.packages('dplyr')
  library(plyr)
  library(stringr)  # install.packages('stringr')
}

## load scenario configuration
conf <- ohicore::Conf("conf")

## check that scenario layers files in the layers folder match layers.csv registration. Layers files are not modified.
ohicore::CheckLayers("layers.csv", "layers", flds_id = conf$config$layers_id_fields)

## load scenario layers for ohicore to access. Layers files are not modified.
layers <- ohicore::Layers("layers.csv", "layers")
layers$data$scenario_year <- 2024

## calculate scenario scores
scores <- ohicore::CalculateAll(conf, layers)

## save scores as scores_2024_r.csv in the scenario directory
setwd(owd)
write.csv(scores, "comparative/scores_2024_r.csv", na = "NA", row.names = FALSE)
