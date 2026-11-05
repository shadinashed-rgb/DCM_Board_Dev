#!/usr/bin/env sh
set -eu
COHORT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "${PYTHON_BIN:-python3}" "$COHORT_DIR/cohort.py" "$@"
