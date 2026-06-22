from __future__ import annotations

import os
from pathlib import Path

import run as backend_run


def test_configure_bundled_node_prepends_resource_bin(tmp_path, monkeypatch):
    resource_dir = tmp_path / "resources"
    node_bin = resource_dir / "nodejs" / ("bin" if os.name != "nt" else "")
    node_bin.mkdir(parents=True)
    existing_bin = tmp_path / "existing-bin"
    existing_bin.mkdir()
    monkeypatch.setenv("PATH", str(existing_bin))

    backend_run._configure_bundled_node(str(resource_dir))

    path_parts = os.environ["PATH"].split(os.pathsep)
    assert path_parts[0] == str(node_bin)
    assert path_parts[1] == str(existing_bin)


def test_configure_bundled_node_leaves_path_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")

    backend_run._configure_bundled_node(str(tmp_path / "resources"))

    assert os.environ["PATH"] == "/usr/bin"


def test_pyinstaller_spec_keeps_protobuf_for_e2b_sandbox():
    spec_path = Path(__file__).resolve().parents[2] / "openyak.spec"
    spec_text = spec_path.read_text(encoding="utf-8")
    excludes_start = spec_text.index("    excludes=[")
    excludes_end = spec_text.index("    ],", excludes_start)
    excludes_block = spec_text[excludes_start:excludes_end]

    assert "'google.protobuf'" not in excludes_block
