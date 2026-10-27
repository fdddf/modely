"""Unit tests for shared download reliability helpers."""

import pytest

from modely.reliability import checksum_status, diagnose_download_error, is_permanent_download_error, normalize_download_options, retry_call


def test_normalize_download_options_validates_values():
    with pytest.raises(ValueError):
        normalize_download_options(retries=-1)
    with pytest.raises(ValueError):
        normalize_download_options(timeout=0)
    with pytest.raises(ValueError):
        normalize_download_options(max_workers=0)


def test_retry_call_retries_until_success():
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary")
        return "ok"

    assert retry_call(flaky, retries=1, label="flaky") == "ok"
    assert calls["count"] == 2


def test_retry_call_does_not_retry_permanent_error():
    calls = {"count": 0}

    def missing():
        calls["count"] += 1
        raise RuntimeError("404 Not Found")

    with pytest.raises(Exception, match="non-retryable"):
        retry_call(missing, retries=3, label="missing")
    assert calls["count"] == 1


def test_retry_call_still_retries_timeout():
    calls = {"count": 0}

    def timeout_then_ok():
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("timeout")
        return "ok"

    assert retry_call(timeout_then_ok, retries=1, label="timeout") == "ok"
    assert calls["count"] == 2


def test_permanent_error_detection():
    assert is_permanent_download_error(RuntimeError("401 Unauthorized")) is True
    assert is_permanent_download_error(RuntimeError("403 Forbidden")) is True
    assert is_permanent_download_error(RuntimeError("404 Not Found")) is True
    assert is_permanent_download_error(RuntimeError("503 Service Unavailable")) is False


def test_checksum_status_verifies_file(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("hello")
    expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    status = checksum_status(str(path), expected)

    assert status.ok is True
    assert status.skipped is False
    assert status.actual == expected


def test_checksum_status_skips_missing_expected(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("hello")

    status = checksum_status(str(path), None)

    assert status.ok is True
    assert status.skipped is True
    assert status.reason == "missing-expected-sha256"


def test_diagnose_download_error_adds_auth_hint():
    message = diagnose_download_error("hf", Exception("401 Unauthorized"))
    assert "authentication failed" in message
