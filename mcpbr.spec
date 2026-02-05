# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for mcpbr
# Build with: pyinstaller mcpbr.spec

import os
import sys
from pathlib import Path

block_cipher = None

# Determine the project root
spec_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(spec_dir, "src", "mcpbr", "__main__.py")],
    pathex=[spec_dir],
    binaries=[],
    datas=[
        (os.path.join(spec_dir, "src", "mcpbr", "data"), "mcpbr/data"),
    ],
    hiddenimports=[
        "mcpbr",
        "mcpbr.cli",
        "mcpbr.config",
        "mcpbr.harness",
        "mcpbr.models",
        "mcpbr.providers",
        "mcpbr.evaluation",
        "mcpbr.reporting",
        "mcpbr.benchmarks",
        "mcpbr.benchmarks.swebench",
        "mcpbr.benchmarks.humaneval",
        "mcpbr.benchmarks.mbpp",
        "click",
        "rich",
        "pydantic",
        "pydantic_settings",
        "yaml",
        "docker",
        "anthropic",
        "mcp",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "scipy",
        "numpy",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="mcpbr",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
