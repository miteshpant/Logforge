"""docs/api/openapi.yaml and openapi.json are the same document."""

import importlib.util
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _exporter():
    spec = importlib.util.spec_from_file_location("export_openapi", ROOT / "scripts" / "export_openapi.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_yaml_and_json_render_the_same_document():
    exporter = _exporter()
    spec = {
        "paths": {"/b": {}, "/a": {"get": {"summary": "é"}}},
        "info": {"title": "t", "version": "1"},
        "openapi": "3.1.0",
        "components": {},
    }
    files = exporter.render(spec)
    as_json = json.loads(files[exporter.OUT])
    as_yaml = yaml.safe_load(files[exporter.OUT_YAML])

    assert as_json == as_yaml == spec
    assert files[exporter.OUT_YAML].startswith("openapi: 3.1.0\ninfo:")


def test_committed_files_agree():
    as_json = json.loads((ROOT / "docs" / "api" / "openapi.json").read_text())
    as_yaml = yaml.safe_load((ROOT / "docs" / "api" / "openapi.yaml").read_text())
    assert as_json == as_yaml
