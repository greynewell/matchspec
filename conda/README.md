# Conda Package for mcpbr

Install mcpbr via conda/mamba.

## Installation

### From conda-forge (when available)

```bash
conda install -c conda-forge mcpbr
```

### Build locally

```bash
conda build conda/
conda install --use-local mcpbr
```

## Building the Package

### Prerequisites

```bash
conda install conda-build
```

### Build

```bash
cd /path/to/mcpbr
conda build conda/
```

### Test

```bash
conda build conda/ --test
```

## Updating

When releasing a new version:

1. Update `version` in `conda/meta.yaml`
2. Update the `sha256` hash from PyPI
3. Update dependency versions if changed
4. Build and test locally before publishing

## Notes

- The `PLACEHOLDER_SHA256` in `meta.yaml` must be replaced with the actual hash from PyPI
- The package is `noarch: python` since mcpbr is pure Python
- Uses `docker-py` (conda name) instead of `docker` (PyPI name)
