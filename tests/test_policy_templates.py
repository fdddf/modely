"""Unit tests for policy templates."""

import json

from modely.policy import policy_template, write_policy_template


def test_policy_template_balanced_contains_governance_controls():
    template = policy_template("balanced")

    assert template["fail_on"] == "medium"
    assert "deny_licenses" in template
    assert "deny_finding_ids" in template
    assert template["min_score"] == 60


def test_write_policy_template(tmp_path):
    output = tmp_path / "policy.json"

    template = write_policy_template("strict", str(output))

    saved = json.loads(output.read_text())
    assert saved == template
    assert saved["require_checksums"] is True
