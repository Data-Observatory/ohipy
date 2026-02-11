# Use R 4.2.3 as base
FROM rocker/r-ver:4.2.3

# Set environment to non-interactive
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git wget libcurl4-openssl-dev libssl-dev libxml2-dev \
    libfontconfig1-dev libfreetype6-dev libgit2-dev \
    libx11-dev pandoc zlib1g-dev \
    && wget -q http://archive.ubuntu.com/ubuntu/pool/main/i/icu/libicu66_66.1-2ubuntu2_amd64.deb \
    && dpkg -i libicu66_66.1-2ubuntu2_amd64.deb \
    && rm libicu66_66.1-2ubuntu2_amd64.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a directory for the renv environment outside of the project directory
WORKDIR /opt/renv-environment

# Copy the setup script
COPY setup_renv.R .

# Run the setup script to create the renv environment
RUN Rscript --vanilla setup_renv.R

# Create project directory
WORKDIR /home/project

ENV R_LIBS=/opt/renv-environment/renv/library/R-4.2/x86_64-pc-linux-gnu

# Default command
CMD ["R"]