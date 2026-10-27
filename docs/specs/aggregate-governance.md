# Spec: modely-ai Aggregate Governance Commands

## Positioning

This document describes the existing and compatibility-oriented aggregate governance CLI for modely-ai: source diagnostics, selection, mirror verification, local lock/install, catalog gate, cache dedupe, reports, benchmarking, and drift checks. It is not the sole enterprise platform CLI authority. The target enterprise command map, aliases, exit codes, and Phase 1-4 command ownership live in `docs/specs/enterprise-cli.md`.

Compatibility rules:

- Existing commands in this file should keep working unless a later migration explicitly deprecates them.
- `modely-ai catalog gate` remains a compatibility CI gate for catalog/report inputs; enterprise documentation should prefer `modely-ai policy check` for policy, lockfile, and approved-asset gates.
- `modely-ai lock RESOURCE ...` and `modely-ai install -f modely.lock` remain local/aggregate lockfile flows; enterprise approved resolution/install is additive.
- HTML reports in this spec are local/compatibility report output. Enterprise Phase 2 baseline reports are JSON/Markdown/CSV; Phase 4 may add HTML compliance reports when a concrete schema/workflow is selected.

## Objective

modely-ai is a cross-platform AI model asset manager rather than a single-source downloader. This feature set promotes modely-ai into an AI asset governance CLI for discovering, diagnosing, selecting, verifying, reporting, and governing model assets across Hugging Face, ModelScope, GitHub, and Kaggle.

Target users:

- Individual developers choosing where to download a model from.
- Enterprise AI platform and MLOps teams enforcing model admission, audit, and mirror consistency.
- CI/CD workflows that need policy gates, lockfile installs, and model risk checks.

Core user stories:

1. Diagnose a query or URI and get a recommended resource, health score, risk level, and next command:

   ```bash
   modely-ai doctor qwen2.5-7b
   ```

2. Choose the best source according to a strategy:

   ```bash
   modely-ai choose qwen2.5-7b --strategy safest
   ```

3. Gate a catalog report in CI:

   ```bash
   modely-ai catalog gate catalog.json --fail-on high --policy policy.json
   ```

4. Verify whether two resources appear mirror-equivalent:

   ```bash
   modely-ai verify-mirror hf://models/org/model ms://models/org/model
   ```

5. Create and install lockfiles with fallback source metadata:

   ```bash
   modely-ai lock hf://models/gpt2 --alternatives hf,ms -o modely.lock
   modely-ai install -f modely.lock --fallback --prefer ms,hf
   ```

6. Report duplicate cache blobs without changing files:

   ```bash
   modely-ai cache dedupe --dry-run --json
   ```

7. Generate resource reports:

   ```bash
   modely-ai report hf://models/gpt2 --format markdown
   modely-ai report ./models/local-model --format html
   ```

8. Probe source endpoints and detect watched-resource drift:

   ```bash
   modely-ai benchmark --source hf,ms --json
   modely-ai watch drift --config watch.json --json
   ```

## Tech Stack

- Language: Python `>=3.10`
- Packaging: setuptools via `pyproject.toml`
- CLI: `argparse`
- Tests: `pytest`
- Source layout: `src/modely/`
- Runtime dependencies:
  - `requests>=2.25.0`
  - `tqdm>=4.62.0`
  - `huggingface-hub>=0.20.0`
- Optional dependencies:
  - `modelscope>=1.0.0`

No new runtime dependencies are required for this feature set.

## Commands

Development setup:

```bash
pip install -e .
pip install -e ".[dev]"
```

Run CLI locally:

```bash
PYTHONPATH=src modely-ai --help
PYTHONPATH=src modely-ai doctor gpt2 --json
PYTHONPATH=src modely-ai choose gpt2 --strategy safest --json
PYTHONPATH=src modely-ai catalog gate catalog.json --fail-on high --json
PYTHONPATH=src modely-ai verify-mirror hf://models/gpt2 ms://models/AI-ModelScope/gpt2 --json
PYTHONPATH=src modely-ai lock hf://models/gpt2 --alternatives hf,ms -o modely.lock
PYTHONPATH=src modely-ai install -f modely.lock --fallback --prefer ms,hf
PYTHONPATH=src modely-ai cache dedupe --dry-run --json
PYTHONPATH=src modely-ai report hf://models/gpt2 --format markdown
PYTHONPATH=src modely-ai benchmark --source hf --json
PYTHONPATH=src modely-ai watch drift --config watch.json --json
```

Unit tests:

```bash
python -m pytest tests/ -m "not integration"
```

Focused tests for this spec:

```bash
python -m pytest \
  tests/test_doctor.py \
  tests/test_choose.py \
  tests/test_policy.py \
  tests/test_manifest.py \
  tests/test_mirror.py \
  tests/test_report.py \
  tests/test_cache.py \
  tests/test_watch.py \
  -m "not integration"
```

Integration tests, when network is allowed:

```bash
python -m pytest tests/ -m integration
```

## Project Structure

Relevant layout:

```text
src/modely/
  __init__.py              CLI entry point and argparse wiring
  doctor.py                Aggregate resource diagnosis
  choose.py                Source/candidate selection
  mirror.py                Mirror verification built on comparison
  report.py                Markdown/HTML/JSON report rendering
  policy.py                Scan and catalog policy gate evaluation
  manifest.py              Lockfile creation/install/validation
  common/cache.py          Cache info/list/clean/dedupe
  watch.py                 Watch config, run, list, drift
  benchmark.py             Source endpoint benchmark helpers
  resolve.py               Cross-source equivalent-resource resolution
  score.py                 Resource and local path scoring
  scan.py                  Resource and local path scanning
  compare.py               Cross-resource comparison
  catalog.py               Local/cache catalog scan/diff/export/history

tests/
  test_doctor.py
  test_choose.py
  test_policy.py
  test_manifest.py
  test_mirror.py
  test_report.py
  test_cache.py
  test_watch.py
```

Documentation:

```text
README.md
CLAUDE.md
docs/specs/aggregate-governance.md
```

## Code Style

Follow existing project style:

- Prefer small pure helper functions.
- Keep CLI output functions separate from data-producing functions.
- Return dictionaries/dataclasses from logic functions; print only in `print_*` helpers or CLI dispatch.
- Use `json.dumps(..., indent=2, ensure_ascii=False)` for JSON output.
- Avoid new dependencies when stdlib is enough.
- Keep errors simple and surfaced as `Error: ...` in CLI dispatch.

Example style:

```python
def evaluate_catalog_policy(report: CatalogReport, *, fail_on: Optional[str] = None, policy: Optional[dict] = None) -> dict:
    """Evaluate catalog entry scan summaries against policy."""
    policy = policy or {}
    threshold = fail_on or policy.get("fail_on")
    ignored_ids = set(policy.get("ignore_finding_ids") or [])
    blocked = []
    allowed = []

    for entry in report.entries:
        scan = entry.scan or {}
        finding_ids = [fid for fid in scan.get("finding_ids", []) if fid not in ignored_ids]
        risk = _risk_from_finding_ids(finding_ids, scan.get("risk_level") or "none")
        # ...
```

CLI pattern:

```python
elif args.command == "doctor":
    try:
        print_doctor_report(
            doctor_resource(
                args.query,
                source=args.source,
                repo_type=args.repo_type,
                probe=args.probe,
                limit=args.limit,
                threshold=args.threshold,
                token=args.token,
                endpoint=args.endpoint,
            ),
            as_json=args.json,
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
```

Testing style:

```python
def test_report_supports_local_path(tmp_path):
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "weights.pkl").write_text("pickle")

    text = create_resource_report(str(tmp_path), format="markdown")

    assert f"- Recommended: `{tmp_path}`" in text
    assert "- Risk: high" in text
```

## Testing Strategy

Use pytest.

Test levels:

1. Unit tests for pure helpers:
   - `doctor_resource`
   - `choose_resource`
   - `evaluate_catalog_policy`
   - `verify_mirror`
   - `create_resource_report`
   - `find_duplicate_files`
   - `check_drift`

2. CLI behavior tests where practical:
   - Parser wiring and exit behavior should be covered either by direct `main()` invocation or subprocess smoke tests.
   - Avoid network in unit tests.

3. Network-dependent behavior:
   - Mark with `integration`.
   - Do not require network for default test suite.

4. Policy and fallback behavior:
   - Use monkeypatching to avoid real downloads.
   - Verify parameters passed to `download_resource`.

Coverage expectations:

- Each new public command has at least one test covering happy path.
- Each gate/failure behavior has at least one failing-path test.
- TDD bug fixes use Prove-It:
  1. Add failing test.
  2. Confirm failure.
  3. Implement fix.
  4. Confirm focused tests pass.
  5. Run full non-integration suite.

## Boundaries

### Always do

- Preserve existing CLI commands and backwards compatibility.
- Run `python -m pytest tests/ -m "not integration"` before committing code changes.
- Use existing helpers before adding new platform-specific logic.
- Keep `cache dedupe` non-destructive unless a future spec explicitly approves mutation.
- Keep `verify-mirror` read-only.
- Keep unit tests offline by default.

### Ask first

- Adding dependencies.
- Changing package name, entrypoint, or public command names.
- Introducing a database or persistent server.
- Making `cache dedupe` delete/link files.
- Adding upload/mirror-to-remote behavior.
- Changing lockfile schema in a breaking way.
- Changing default source selection order.

### Never do

- Commit secrets or tokens.
- Write credentials into watch configs.
- Remove tests to make a suite pass.
- Make network integration tests part of the default unit suite.
- Delete user cache/model files without explicit destructive confirmation.
- Silently ignore policy failures in CI-facing commands.

## Success Criteria

This feature set is complete when:

1. `modely-ai doctor QUERY --json` returns `query`, `recommended`, `score`, `scan`, `warnings`, and `next_steps`.
2. `modely-ai choose QUERY --strategy safest --json` returns `recommended`, ranked `candidates`, and ranking reasons.
3. `modely-ai catalog gate catalog.json --fail-on high --json` exits 1 when blocked, exits 0 when allowed, and honors `ignore_finding_ids`.
4. `modely-ai verify-mirror LEFT RIGHT --json` returns `status: ok` or `status: drifted` with reasons and comparison detail.
5. `modely-ai lock RESOURCE --alternatives hf,ms -o modely.lock` records alternatives in lock metadata.
6. `modely-ai install -f modely.lock --fallback --prefer ms,hf` passes fallback source order into download logic.
7. `modely-ai cache dedupe --dry-run --json` reports duplicate groups and reclaimable bytes without modifying files.
8. `modely-ai report RESOURCE --format markdown|html|json` supports remote resources and local paths using local score/scan.
9. `modely-ai benchmark --source hf --json` returns endpoint availability/latency info.
10. `modely-ai watch drift --config watch.json --json` reports drifted/unchanged/error without downloading or updating watch state.
11. Full unit suite passes:

```bash
python -m pytest tests/ -m "not integration"
```

## Open Questions

1. Should README updates be committed in the same change or as a separate documentation pass?
2. Should `doctor` and `choose` support local paths directly, or should local path diagnosis remain under `report`, `score`, and `scan`?
3. Should `catalog gate` eventually reconstruct full `ScanResult` objects for richer policy checks, or keep summary-only gate semantics?
4. Should `cache dedupe` later support hardlinking/deletion behind explicit flags?
