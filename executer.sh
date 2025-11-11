#!/bin/sh
set -eu

usage() {
    printf 'Usage: %s DATA_DIR INPUT_FILE OUTPUT_FILE\n' "$(basename "$0")" >&2
    exit 2
}

[ "$#" -eq 3 ] || usage

DATA_DIR=$1
INPUT=$2
OUTPUT=$3

HOST_UID=$(id -u)
HOST_GID=$(id -g)

if [ ! -d "$DATA_DIR" ]; then
    printf 'Error: data directory not found: %s\n' "$DATA_DIR" >&2
    exit 1
fi

if [ ! -e "$DATA_DIR/$INPUT" ]; then
    printf 'Error: input file not found: %s\n' "$DATA_DIR/$INPUT" >&2
    exit 1
fi

# Ensure output directory exists
OUT_DIR=$(dirname "$DATA_DIR/$OUTPUT")
if [ ! -d "$OUT_DIR" ]; then
    mkdir -p "$OUT_DIR"
fi

# Run containerized movie normalizer
docker run --rm \
    -u $(id -u):$(id -g) \
    -v "$DATA_DIR":/data movie-normalizer \
    "/data/$INPUT" "/data/$OUTPUT"