#!/usr/bin/env bash
set -euo pipefail

# Entrypoint for the mcpbr Docker image.
# Passes all arguments to the mcpbr CLI.

# If the first argument looks like a subcommand (not a flag), run mcpbr directly
# Otherwise, if it's a raw command (e.g., bash, sh), execute it directly
case "${1:-}" in
    bash|sh|/bin/bash|/bin/sh)
        exec "$@"
        ;;
    *)
        exec mcpbr "$@"
        ;;
esac
