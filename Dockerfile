#############################
# Builder stage: install Python deps into a venv
#############################
FROM python:3.14-slim AS builder

# Install system packages required to build Python wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl gcc libffi-dev libssl-dev \
    zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install Poetry
RUN pip install --no-cache-dir poetry
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_CREATE=true
# Create venv
RUN python -m venv /opt/venv

# Copy pyproject and application source. Copying only pyproject first
# leverages Docker cache when dependencies don't change.
COPY pyproject.toml /build/
COPY app/ /build/app

# Create venv with poetry and install dependencies
WORKDIR /build/app
RUN poetry env use /opt/venv/bin/python
RUN poetry install --without dev --no-interaction


#############################
# Final runtime image
#############################
FROM python:3.14-slim

# Update repo and install only runtime packages
RUN apt-get clean && apt-get update --fix-missing
RUN apt-get install -y \ 
    --no-install-recommends \
    ffmpeg opus-tools libopus-dev mkvtoolnix
# Cleanup apt cache
RUN rm -rf /var/lib/apt/lists/*

# Copy virtualenv and application from builder
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build/app /app

ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Expose the CLI as the container entrypoint. Run like:
# docker run --rm -v /path/to/files:/data <image> /data/input.mkv /data/output.mkv
# The two positional args are forwarded to the script as file_path_input and file_path_output.
ENTRYPOINT ["python", "app.py"]

