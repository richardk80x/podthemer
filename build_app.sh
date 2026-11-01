#!/bin/bash
set -euo pipefail
builder_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
if [[ $# -ne 2 ]]; then
  printf 'Usage: bash build_app.sh WORK_DIRECTORY OUTPUT_APP_PATH\nUse a build Python with requirements-build.txt installed.\n'
  exit 2
fi
"${PODTHEMER_BUILD_PYTHON:-python3}" "$builder_dir/build_release.py" --work "$1" --output "$2"
