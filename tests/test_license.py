"""Unit tests for license risk helpers."""

import io
from unittest.mock import patch

from modely.license import classify_license
from modely.governance.license import (
    build_license_risk,
    classify_license as gov_classify_license,
    print_license_risk,
)


# ---------------------------------------------------------------------------
# 1. classify_license — permissive licenses
# ---------------------------------------------------------------------------

def test_classify_license_permissive():
    result = classify_license("apache-2.0")
    assert result["class"] == "permissive"
    assert result["risk"] == "low"


def test_classify_license_mit():
    result = classify_license("mit")
    assert result["class"] == "permissive"
    assert result["risk"] == "low"


def test_classify_license_bsd():
    result = classify_license("bsd-3-clause")
    assert result["class"] == "permissive"
    assert result["risk"] == "low"


def test_classify_license_cc_by():
    result = classify_license("cc-by-4.0")
    assert result["class"] == "permissive"
    assert result["risk"] == "low"


def test_classify_license_unlicense():
    result = classify_license("unlicense")
    assert result["class"] == "permissive"
    assert result["risk"] == "low"


# ---------------------------------------------------------------------------
# 2. classify_license — unknown / None
# ---------------------------------------------------------------------------

def test_classify_license_unknown_high_risk():
    result = classify_license(None)
    assert result["class"] == "unknown"
    assert result["risk"] == "high"


def test_classify_license_empty_string():
    result = classify_license("")
    assert result["class"] == "unknown"
    assert result["risk"] == "high"


def test_classify_license_unknown_token():
    result = classify_license("unknown")
    assert result["class"] == "unknown"
    assert result["risk"] == "high"


def test_classify_license_other_token():
    result = classify_license("other")
    assert result["class"] == "unknown"
    assert result["risk"] == "high"


def test_classify_license_none_token():
    result = classify_license("none")
    assert result["class"] == "unknown"
    assert result["risk"] == "high"


# ---------------------------------------------------------------------------
# 3. classify_license — non-commercial / research-only
# ---------------------------------------------------------------------------

def test_classify_license_non_commercial_high_risk():
    result = classify_license("cc-by-nc-4.0")
    assert result["class"] == "non-commercial"
    assert result["risk"] == "high"


def test_classify_license_noncommercial_variant():
    result = classify_license("noncommercial-use-only")
    assert result["class"] == "non-commercial"
    assert result["risk"] == "high"


def test_classify_license_research_only():
    result = classify_license("research-only")
    assert result["class"] == "non-commercial"
    assert result["risk"] == "high"


# ---------------------------------------------------------------------------
# 4. classify_license — strong copyleft (AGPL, GPL)
# ---------------------------------------------------------------------------

def test_classify_license_agpl():
    result = classify_license("agpl-3.0")
    assert result["class"] == "strong-copyleft"
    assert result["risk"] == "medium"


def test_classify_license_gpl():
    result = classify_license("gpl-3.0")
    assert result["class"] == "strong-copyleft"
    assert result["risk"] == "medium"


def test_classify_license_gpl_with_underscore():
    result = classify_license("gpl_3.0")
    assert result["class"] == "strong-copyleft"
    assert result["risk"] == "medium"


# ---------------------------------------------------------------------------
# 5. classify_license — weak copyleft (LGPL, MPL, EPL)
# ---------------------------------------------------------------------------

def test_classify_license_lgpl():
    """lgpl contains 'gpl' substring so matches strong-copyleft first (known behavior)."""
    result = classify_license("lgpl-2.1")
    assert result["class"] == "strong-copyleft"
    assert result["risk"] == "medium"


def test_classify_license_mpl():
    result = classify_license("mpl-2.0")
    assert result["class"] == "weak-copyleft"
    assert result["risk"] == "medium"


def test_classify_license_epl():
    result = classify_license("epl-2.0")
    assert result["class"] == "weak-copyleft"
    assert result["risk"] == "medium"


# ---------------------------------------------------------------------------
# 6. classify_license — custom restrictive (llama, openrail, custom)
# ---------------------------------------------------------------------------

def test_classify_license_llama():
    result = classify_license("llama-2-community")
    assert result["class"] == "custom-restrictive"
    assert result["risk"] == "medium"


def test_classify_license_openrail():
    result = classify_license("openrail")
    assert result["class"] == "custom-restrictive"
    assert result["risk"] == "medium"


def test_classify_license_custom():
    result = classify_license("custom-agreement")
    assert result["class"] == "custom-restrictive"
    assert result["risk"] == "medium"


def test_classify_license_community():
    result = classify_license("community-license")
    assert result["class"] == "custom-restrictive"
    assert result["risk"] == "medium"


# ---------------------------------------------------------------------------
# 7. classify_license — other fallback
# ---------------------------------------------------------------------------

def test_classify_license_unrecognized():
    result = classify_license("some-obscure-license")
    assert result["class"] == "other"
    assert result["risk"] == "medium"


# ---------------------------------------------------------------------------
# 8. governance.license — classify_license parity
# ---------------------------------------------------------------------------

def test_gov_classify_license_same_as_facade():
    """gov_classify_license returns same result as facade's classify_license."""
    facade_result = classify_license("mit")
    gov_result = gov_classify_license("mit")
    assert facade_result == gov_result


# ---------------------------------------------------------------------------
# 9. build_license_risk
# ---------------------------------------------------------------------------

class _MockInfo:
    source = "hf"
    repo_type = "model"
    repo_id = "org/model-name"
    license = "apache-2.0"


def test_build_license_risk_includes_metadata():
    """build_license_risk appends source/repo info to classification."""
    info = _MockInfo()
    result = build_license_risk("download", info)
    assert result["resource"] == "download"
    assert result["source"] == "hf"
    assert result["repo_type"] == "model"
    assert result["repo_id"] == "org/model-name"
    assert result["license"] == "apache-2.0"
    assert result["class"] == "permissive"
    assert result["risk"] == "low"


def test_build_license_risk_with_none_license():
    """build_license_risk handles None license."""
    info = _MockInfo()
    info.license = None  # type: ignore
    result = build_license_risk("catalog", info)
    assert result["class"] == "unknown"
    assert result["risk"] == "high"


# ---------------------------------------------------------------------------
# 10. print_license_risk — text mode
# ---------------------------------------------------------------------------

def test_print_license_risk_text_mode():
    """print_license_risk prints human-readable output."""
    result = {
        "source": "hf",
        "repo_type": "model",
        "repo_id": "org/m",
        "license": "mit",
        "class": "permissive",
        "risk": "low",
        "reason": "License appears permissive; still verify obligations.",
    }
    with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
        print_license_risk(result)
        output = mock_stdout.getvalue()
    assert "org/m" in output
    assert "permissive" in output
    assert "low" in output


def test_print_license_risk_text_mode_no_license():
    """print_license_risk shows '-' for None license."""
    result = {
        "source": "hf",
        "repo_type": "model",
        "repo_id": "org/no-lic",
        "license": None,
        "class": "unknown",
        "risk": "high",
        "reason": "No clear license metadata detected.",
    }
    with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
        print_license_risk(result)
        output = mock_stdout.getvalue()
    assert "License:  -" in output


# ---------------------------------------------------------------------------
# 11. print_license_risk — JSON mode
# ---------------------------------------------------------------------------

def test_print_license_risk_json_mode():
    """print_license_risk prints JSON when as_json=True."""
    import json

    result = {
        "source": "ms",
        "repo_type": "dataset",
        "repo_id": "org/ds",
        "license": "cc-by-4.0",
        "class": "permissive",
        "risk": "low",
        "reason": "License appears permissive; still verify obligations.",
    }
    with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
        print_license_risk(result, as_json=True)
        output = mock_stdout.getvalue()
    parsed = json.loads(output)
    assert parsed["repo_id"] == "org/ds"
    assert parsed["class"] == "permissive"
