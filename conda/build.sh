#!/bin/bash
# Conda build script for mcpbr (Unix/macOS)
set -euo pipefail

${PYTHON} -m pip install . --no-deps --no-build-isolation -vv
