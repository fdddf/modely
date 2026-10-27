"""Server route and reporting contract tests."""

from __future__ import annotations

from modely.reporting.csv import format_csv
from modely.reporting.json import format_json
from modely.reporting.markdown import format_markdown
from modely.reporting.sarif import format_sarif
from modely.server.routes.health import get_health
from modely.types import ScanFinding


def test_health_route_contract_includes_service_identity():
    payload = get_health()

    assert payload["data"]["status"] == "ok"
    assert payload["data"]["service"] == "modely-server"
    assert "version" in payload["data"]
    assert "request_id" in payload["meta"]
    assert payload["meta"]["schema_version"] == "v1"


def test_reporting_formatters_have_stable_minimal_output():
    finding = ScanFinding(id="secret", severity="high", category="security", message="secret found", path="config.env")

    assert "# modely report" in format_markdown({"resource": "hf://models/gpt2"})
    assert '"resource": "hf://models/gpt2"' in format_json({"resource": "hf://models/gpt2"})
    assert format_csv([{"name": "gpt2", "risk": "low"}]).replace("\r\n", "\n") == "name,risk\ngpt2,low\n"

    sarif = format_sarif([finding])
    result = sarif["runs"][0]["results"][0]
    assert sarif["version"] == "2.1.0"
    assert result["ruleId"] == "secret"
    assert result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "config.env"
