#!/usr/bin/env Rscript
# create_lockfile.R - Non-interactive creation of a locked renv with dplyr@1.0.10 and ohicore

# 1. Set CRAN snapshot to 2022-10-01 (contains dplyr 1.0.10)
options(repos = c(CRAN = "https://packagemanager.posit.co/cran/__linux__/jammy/2022-10-01"))
cat("1. Repository set to 2022-10-01 snapshot.\n")

# 2. Install renv
install.packages("renv", quiet = TRUE)
cat("2. Installed renv.\n")

# 3. Initialize a bare renv project
renv::init(bare = TRUE, restart = FALSE)
cat("3. Initialized bare renv project.\n")

# 4. INSTALL CORE PACKAGES FROM SNAPSHOT
#    This pins them to versions available on 2022-10-01
target_packages <- c("dplyr", "tidyr", "tibble", "purrr", "stringr", "ggplot2", "plyr", "zoo", "remotes", "yaml",
                    "git2r", "htmlwidgets", "here", "plotly", "reshape2", "tidyverse")
renv::install(target_packages, prompt = FALSE)
cat("4. Installed and pinned core packages from 2022 snapshot.\n")

# 5. CRITICAL STEP: Install ohicore WITHOUT its dependencies
#    This prevents renv from seeing and trying to satisfy its modern dependency tree
cat("5. Cloning ohicore into project directory...\n")

if (!dir.exists("ohicore")) {
  system("git clone --depth 1 https://github.com/ohi-science/ohicore.git")
}

cat("6. Installing ohicore from local source WITHOUT dependencies...\n")

remotes::install_local("ohicore", dependencies = FALSE, quiet = FALSE, upgrade = "never")

# 7. Force a snapshot to create the lockfile
cat("7. Creating final lockfile...\n")
renv::snapshot(confirm = FALSE, prompt = FALSE, force = TRUE)

# 8. FINAL VERIFICATION: Fail the script if dplyr is not 1.0.10
final_version <- packageVersion("dplyr")
cat("8. FINAL CHECK: dplyr version is", as.character(final_version), "\n")
if (final_version != "1.0.10") {
  stop("ERROR: dplyr version is not 1.0.10. Build failed.")
}

cat("\n✅ SUCCESS: renv.lock created with dplyr@1.0.10 and ohicore.\n")
cat("   The following files are ready for your Dockerfile:\n")
cat("   - renv.lock\n")
cat("   - .Rprofile\n")
cat("   - renv/ folder\n")