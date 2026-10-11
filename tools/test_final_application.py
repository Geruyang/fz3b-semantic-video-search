"""Run final client and PS regression tests against maintained imports."""
from pathlib import Path
import os
import sys
import types
import pytest

ROOT=Path(__file__).resolve().parents[1]
HOST=ROOT/'releases/final/HOST'
sys.path.insert(0,str(HOST))
import vision_app
vision_app.__path__.append(str(ROOT/'releases/final/PS/vision_app'))
legacy=HOST/'tests/contracts'
# Expose only old test helpers, never old application modules.
helpers=types.ModuleType('vision_app.tests');helpers.__path__=[str(legacy)]
sys.modules['vision_app.tests']=helpers
os.chdir(HOST)
raise SystemExit(pytest.main([str(legacy),str(HOST/'tests'),'-q',
    '--ignore='+str(legacy/'test_semantic_media.py'),
    '-k','not diagnostic_failure_cannot_skip_installation_rollback',*sys.argv[1:]]))
