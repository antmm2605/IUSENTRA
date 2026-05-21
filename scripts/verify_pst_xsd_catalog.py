#!/usr/bin/env python3
"""Compatibilità: alias di validate_codici_oggetto_pst.py."""
from __future__ import annotations
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.argv[0] = str(ROOT / "scripts" / "validate_codici_oggetto_pst.py")
runpy.run_path(sys.argv[0], run_name="__main__")
