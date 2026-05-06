# Lightweight OHI Python calculator
# Build:  docker build -t ohipy .
# Run:    docker run --rm -v $(pwd)/results:/output ohipy
# Custom: docker run --rm -v /path/to/data:/app/data -v $(pwd)/results:/output ohipy --year 2023

FROM python:3.14.2-slim

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# --- Dependency layer (cached unless pyproject.toml changes) ---
COPY pyproject.toml .
COPY src/ src/
RUN uv pip install --system --no-cache .

# --- Application layer ---
COPY scripts/ scripts/
COPY data/ data/

# Default output directory (mount a host volume here to get results)
RUN mkdir -p /output

ENTRYPOINT ["python", "scripts/run_python_scores.py"]
CMD ["--output", "/output/scores.csv"]
