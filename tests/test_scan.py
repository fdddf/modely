"""Unit tests for asset risk scanning."""

import json

from modely.scan import print_scan_result, risk_level, scan_path, scan_resource, summarize_findings
from modely.types import AssetAnalysis, FileInfo, FileSummary, RepoInfo, ScanFinding


def _analysis(**overrides):
    info = overrides.pop("info", RepoInfo("hf", "model", "org/model", license="mit"))
    files = overrides.pop("files", [
        FileInfo("README.md", size=10, sha256="a"),
        FileInfo("config.json", size=20, sha256="b"),
        FileInfo("tokenizer.json", size=30, sha256="c"),
        FileInfo("model.safetensors", size=1000, sha256="d"),
    ])
    defaults = {
        "info": info,
        "summary": FileSummary(total_files=len(files), selected_files=len(files), selected_size=sum(f.size for f in files)),
        "files": files,
        "weight_formats": {"safetensors": 1},
        "has_config": True,
        "has_tokenizer": True,
        "has_card": True,
        "metadata": {"deep": {"risk_flags": [], "weight_bytes": 1000}},
    }
    defaults.update(overrides)
    return AssetAnalysis(**defaults)


def test_scan_missing_metadata_findings(monkeypatch):
    analysis = _analysis(
        info=RepoInfo("hf", "model", "org/model", license=None),
        has_card=False,
        has_config=False,
        has_tokenizer=False,
    )
    monkeypatch.setattr("modely.scan.analyze_resource", lambda *a, **k: analysis)

    result = scan_resource("hf://models/org/model")
    ids = {f.id for f in result.findings}

    assert result.risk_level == "high"
    assert "missing-license" in ids
    assert "missing-card" in ids
    assert "missing-config" in ids
    assert "missing-tokenizer" in ids


def test_scan_pickle_is_high_severity(monkeypatch):
    analysis = _analysis(files=[FileInfo("weights.pkl", size=10, sha256="x")])
    monkeypatch.setattr("modely.scan.analyze_resource", lambda *a, **k: analysis)

    result = scan_resource("hf://models/org/model")

    finding = next(f for f in result.findings if f.id == "pickle-artifact")
    assert finding.severity == "high"
    assert finding.category == "security"


def test_scan_unsafe_weight_format_recommends_safetensors(monkeypatch):
    analysis = _analysis(files=[FileInfo("pytorch_model.bin", size=10, sha256="x")])
    monkeypatch.setattr("modely.scan.analyze_resource", lambda *a, **k: analysis)

    result = scan_resource("hf://models/org/model")

    finding = next(f for f in result.findings if f.id == "unsafe-weight-format")
    assert finding.severity == "medium"
    assert "safetensors" in finding.recommendation


def test_scan_remote_code_and_scripts(monkeypatch):
    analysis = _analysis(files=[
        FileInfo("modeling_custom.py", size=10, sha256="x"),
        FileInfo("run.sh", size=10, sha256="y"),
    ])
    monkeypatch.setattr("modely.scan.analyze_resource", lambda *a, **k: analysis)

    ids = {f.id for f in scan_resource("hf://models/org/model").findings}

    assert "remote-code" in ids
    assert "script-file" in ids


def test_scan_secret_file_is_high_severity(monkeypatch):
    analysis = _analysis(files=[FileInfo(".env", size=10, sha256="x")])
    monkeypatch.setattr("modely.scan.analyze_resource", lambda *a, **k: analysis)

    result = scan_resource("hf://models/org/model")

    finding = next(f for f in result.findings if f.id == "secret-file")
    assert finding.severity == "high"


def test_scan_local_secret_patterns(tmp_path):
    (tmp_path / "README.md").write_text("token hf_abcdefghijklmnopqrstuvwxyz123456")

    result = scan_path(str(tmp_path))

    assert any(f.id == "possible-token" for f in result.findings)


def test_scan_missing_checksums(monkeypatch):
    analysis = _analysis(files=[FileInfo("config.json", size=10)])
    monkeypatch.setattr("modely.scan.analyze_resource", lambda *a, **k: analysis)

    result = scan_resource("hf://models/org/model")

    assert any(f.id == "missing-checksums" for f in result.findings)


def test_scan_summary_and_risk_level():
    findings = [
        ScanFinding("a", "low", "x", "low"),
        ScanFinding("b", "medium", "x", "medium"),
    ]

    assert risk_level(findings) == "medium"
    assert summarize_findings(findings) == {"high": 0, "medium": 1, "low": 1, "total": 2}


def test_scan_json_output(monkeypatch, capsys):
    monkeypatch.setattr("modely.scan.analyze_resource", lambda *a, **k: _analysis())

    print_scan_result(scan_resource("hf://models/org/model"), as_json=True)
    parsed = json.loads(capsys.readouterr().out)

    assert parsed["resource"] == "hf://models/org/model"
    assert "findings" in parsed


def test_scan_human_output(monkeypatch, capsys):
    monkeypatch.setattr("modely.scan.analyze_resource", lambda *a, **k: _analysis(files=[FileInfo("weights.pkl", size=10)]))

    print_scan_result(scan_resource("hf://models/org/model"))
    out = capsys.readouterr().out

    assert "Risk level" in out
    assert "pickle-artifact" in out


def test_scan_path_reports_local_findings(tmp_path):
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "weights.pkl").write_text("pickle")
    (tmp_path / "modeling_custom.py").write_text("pass")

    result = scan_path(str(tmp_path))
    ids = {f.id for f in result.findings}

    assert "pickle-artifact" in ids
    assert "remote-code" in ids
