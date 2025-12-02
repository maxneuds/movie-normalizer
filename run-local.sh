#!/bin/sh
set -eu

usage() {
    printf 'Usage: %s INPUT_FILE\n' "$(basename "$0")" >&2
    exit 2
}

[ "$#" -eq 1 ] || usage

INPUT_FILE=$1

poetry run python app/main.py \
    "$INPUT_FILE" \
    "${INPUT_FILE%.*}_normalized.${INPUT_FILE##*.}"
