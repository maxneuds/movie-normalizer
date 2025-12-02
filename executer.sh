#!/bin/sh
set -eu

usage() {
    printf 'Usage: %s DATA_DIR FILE_INPUT\n' "$(basename "$0")" >&2
    exit 2
}

[ "$#" -eq 2 ] || usage

DATA_DIR=$1
FILE_INPUT=$2

HOST_UID=$(id -u)
HOST_GID=$(id -g)

if [ ! -d "$DATA_DIR" ]; then
    printf 'Error: data directory not found: %s\n' "$DATA_DIR" >&2
    exit 1
fi

if [ ! -e "$DATA_DIR/$FILE_INPUT" ]; then
    printf 'Error: input file not found: %s\n' "$DATA_DIR/$FILE_INPUT" >&2
    exit 1
fi

# Run containerized movie normalizer
docker run --rm \
    -u $(id -u):$(id -g) \
    -v "$DATA_DIR":/data movie-normalizer \
    "/data/$FILE_INPUT" "/data/${FILE_INPUT%.*}_normalized.${FILE_INPUT##*.}"
