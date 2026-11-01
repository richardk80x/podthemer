#!/bin/bash
set -euo pipefail
builder_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
open -a "$builder_dir/Pod Themer.app"
