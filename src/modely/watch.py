"""
Watch Hugging Face and ModelScope repositories and download changes.

The watch command is intentionally a single-run checker. Recurring execution is
handled by cron so modely does not need to run as a long-lived service.
"""

import argparse
import contextlib
import fnmatch
import hashlib
import io
import json
import os
import shlex
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from huggingface_hub import HfApi

from .hf import hf_file_download, snapshot_download as hf_snapshot_download
from .modelscope import (
    HubApi,
    dataset_file_download,
    model_file_download,
    snapshot_download as modelscope_snapshot_download,
)


DEFAULT_CONFIG_FILE = os.path.join(str(Path.home()), ".modely", "watch.json")
DEFAULT_STATE_FILE = os.path.join(str(Path.home()), ".modely", "watch_state.json")
DEFAULT_LOG_FILE = os.path.join(str(Path.home()), ".modely", "watch.log")
MARKER_PREFIX = "# modely-watch:"
VALID_SOURCES = {"hf", "ms"}
VALID_REPO_TYPES = {"model", "dataset"}
VALID_DOWNLOADS = {"snapshot", "files"}
WEEKDAYS = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}


def _expand_path(path: Optional[str]) -> Optional[str]:
    if path is None:
        return None
    return os.path.abspath(os.path.expandvars(os.path.expanduser(path)))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def target_key(target: Dict) -> str:
    return f"{target['source']}:{target['repo_type']}:{target['repo_id']}:{target['revision']}"


def default_config() -> Dict:
    return {
        "state_file": DEFAULT_STATE_FILE,
        "targets": [],
    }


def init_config(config_path: Optional[str] = None, force: bool = False) -> str:
    path = _expand_path(config_path or DEFAULT_CONFIG_FILE)
    if os.path.exists(path) and not force:
        raise FileExistsError(f"Config already exists: {path}")
    _ensure_parent(path)
    with open(path, "w") as f:
        json.dump(default_config(), f, indent=2)
        f.write("\n")
    return path


def _ensure_string_list(value, field: str, required: bool = False) -> List[str]:
    if value is None:
        if required:
            raise ValueError(f"'{field}' must be a non-empty list")
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"'{field}' must be a list of strings")
    if required and not value:
        raise ValueError(f"'{field}' must be a non-empty list")
    return value


def normalize_target(raw_target: Dict) -> Dict:
    if not isinstance(raw_target, dict):
        raise ValueError("Each watch target must be an object")

    source = raw_target.get("source")
    if source not in VALID_SOURCES:
        raise ValueError("'source' must be one of: hf, ms")

    repo_type = raw_target.get("repo_type", "model")
    if repo_type not in VALID_REPO_TYPES:
        raise ValueError("'repo_type' must be one of: model, dataset")

    repo_id = raw_target.get("repo_id")
    if not isinstance(repo_id, str) or not repo_id:
        raise ValueError("'repo_id' must be a non-empty string")

    revision = raw_target.get("revision")
    if not revision:
        revision = "main" if source == "hf" else "master"
    if not isinstance(revision, str):
        raise ValueError("'revision' must be a string")

    download = raw_target.get("download", "snapshot")
    if download not in VALID_DOWNLOADS:
        raise ValueError("'download' must be one of: snapshot, files")

    files = _ensure_string_list(raw_target.get("files"), "files", required=download == "files")
    allow_patterns = _ensure_string_list(raw_target.get("allow_patterns"), "allow_patterns")
    ignore_patterns = _ensure_string_list(raw_target.get("ignore_patterns"), "ignore_patterns")

    target = {
        "source": source,
        "repo_type": repo_type,
        "repo_id": repo_id,
        "revision": revision,
        "download": download,
        "files": files,
        "allow_patterns": allow_patterns,
        "ignore_patterns": ignore_patterns,
        "cache_dir": _expand_path(raw_target.get("cache_dir")),
        "local_dir": _expand_path(raw_target.get("local_dir")),
        "token_env": raw_target.get("token_env"),
    }
    if target["token_env"] is not None and not isinstance(target["token_env"], str):
        raise ValueError("'token_env' must be a string")
    return target


def load_config(config_path: Optional[str] = None) -> Tuple[Dict, str]:
    path = _expand_path(config_path or DEFAULT_CONFIG_FILE)
    with open(path, "r") as f:
        config = json.load(f)

    targets = config.get("targets")
    if not isinstance(targets, list):
        raise ValueError("'targets' must be a list")

    normalized = [normalize_target(target) for target in targets]
    state_file = _expand_path(config.get("state_file") or DEFAULT_STATE_FILE)
    return {"state_file": state_file, "targets": normalized}, path


def load_state(state_file: str) -> Dict:
    path = _expand_path(state_file)
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)


def save_state(state_file: str, state: Dict) -> None:
    path = _expand_path(state_file)
    _ensure_parent(path)
    with open(path, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


def _token_for_target(target: Dict) -> Optional[str]:
    token_env = target.get("token_env")
    return os.environ.get(token_env) if token_env else None


def _file_digest(files: Iterable[Dict]) -> str:
    normalized = []
    for file_info in files:
        path = file_info.get("Path") or file_info.get("path") or file_info.get("rfilename")
        if not path:
            continue
        normalized.append(
            {
                "path": path,
                "size": file_info.get("Size", file_info.get("size")),
                "sha": file_info.get("Sha256", file_info.get("sha256", file_info.get("blob_id"))),
            }
        )
    payload = json.dumps(sorted(normalized, key=lambda item: item["path"]), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _hf_fingerprint(target: Dict, token: Optional[str]) -> str:
    api = HfApi()
    info = api.repo_info(
        repo_id=target["repo_id"],
        repo_type=target["repo_type"],
        revision=target["revision"],
        token=token,
        files_metadata=True,
    )
    sha = getattr(info, "sha", None)
    if sha:
        return str(sha)

    siblings = getattr(info, "siblings", []) or []
    files = [
        {
            "rfilename": getattr(sibling, "rfilename", None),
            "size": getattr(sibling, "size", None),
            "blob_id": getattr(sibling, "blob_id", None),
        }
        for sibling in siblings
    ]
    return _file_digest(files)


def _modelscope_files(target: Dict, token: Optional[str]) -> List[Dict]:
    api = HubApi(token=token)
    cookies = api.get_cookies()
    endpoint = api.get_endpoint_for_read(target["repo_id"], target["repo_type"])
    with contextlib.redirect_stdout(io.StringIO()):
        if target["repo_type"] == "model":
            return api.get_model_files(
                model_id=target["repo_id"],
                revision=target["revision"],
                recursive=True,
                use_cookies=cookies,
                endpoint=endpoint,
            )
        return api.get_dataset_files(
            dataset_id=target["repo_id"],
            revision=target["revision"],
            recursive=True,
            use_cookies=cookies,
            endpoint=endpoint,
        )


def _ms_fingerprint(target: Dict, token: Optional[str]) -> str:
    files = _modelscope_files(target, token)
    if not files and target["download"] == "files" and target["files"]:
        payload = json.dumps(
            {
                "repo_id": target["repo_id"],
                "repo_type": target["repo_type"],
                "revision": target["revision"],
                "files": target["files"],
                "run_id": uuid.uuid4().hex,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if not files:
        raise RuntimeError(f"Could not list files for ModelScope repository: {target['repo_id']}")
    return _file_digest(files)


def get_remote_fingerprint(target: Dict) -> str:
    token = _token_for_target(target)
    if target["source"] == "hf":
        return _hf_fingerprint(target, token)
    return _ms_fingerprint(target, token)


def _matches_patterns(path: str, allow_patterns: List[str], ignore_patterns: List[str]) -> bool:
    if allow_patterns and not any(fnmatch.fnmatch(path, pattern) for pattern in allow_patterns):
        return False
    if ignore_patterns and any(fnmatch.fnmatch(path, pattern) for pattern in ignore_patterns):
        return False
    return True


def _filtered_modelscope_files(target: Dict, token: Optional[str]) -> List[str]:
    paths = []
    for file_info in _modelscope_files(target, token):
        if file_info.get("Type") == "tree":
            continue
        path = file_info.get("Path")
        if path and _matches_patterns(path, target["allow_patterns"], target["ignore_patterns"]):
            paths.append(path)
    return paths


def download_target(target: Dict) -> Optional[str]:
    token = _token_for_target(target)
    common_kwargs = {
        "revision": target["revision"],
        "cache_dir": target["cache_dir"],
        "local_dir": target["local_dir"],
        "token": token,
    }

    if target["source"] == "hf":
        if target["download"] == "files":
            downloaded = []
            for filename in target["files"]:
                if _matches_patterns(filename, target["allow_patterns"], target["ignore_patterns"]):
                    downloaded.append(
                        hf_file_download(
                            repo_id=target["repo_id"],
                            filename=filename,
                            repo_type=target["repo_type"],
                            force_download=True,
                            **common_kwargs,
                        )
                    )
            return downloaded[-1] if downloaded else None
        return hf_snapshot_download(
            repo_id=target["repo_id"],
            repo_type=target["repo_type"],
            allow_patterns=target["allow_patterns"] or None,
            ignore_patterns=target["ignore_patterns"] or None,
            force_download=True,
            **common_kwargs,
        )

    if target["download"] == "files":
        paths = target["files"]
    elif target["allow_patterns"] or target["ignore_patterns"]:
        paths = _filtered_modelscope_files(target, token)
    else:
        result = modelscope_snapshot_download(
            repo_id=target["repo_id"],
            repo_type=target["repo_type"],
            force_download=True,
            **common_kwargs,
        )
        return result

    downloaded = []
    for file_path in paths:
        if not _matches_patterns(file_path, target["allow_patterns"], target["ignore_patterns"]):
            continue
        if target["repo_type"] == "model":
            downloaded.append(model_file_download(model_id=target["repo_id"], file_path=file_path, **common_kwargs))
        else:
            downloaded.append(dataset_file_download(dataset_id=target["repo_id"], file_path=file_path, **common_kwargs))
    return downloaded[-1] if downloaded else None


def check_target(target: Dict, state: Dict) -> Dict:
    key = target_key(target)
    previous = state.get(key, {})
    try:
        fingerprint = get_remote_fingerprint(target)
        changed = previous.get("fingerprint") != fingerprint
        if changed:
            download_path = download_target(target)
            entry = {
                **previous,
                "fingerprint": fingerprint,
                "last_checked_at": _now_iso(),
                "last_downloaded_at": _now_iso(),
                "last_download_path": download_path,
                "error": None,
            }
            state[key] = entry
            return {"key": key, "target": target, "status": "downloaded", "path": download_path}

        state[key] = {**previous, "last_checked_at": _now_iso(), "error": None}
        return {
            "key": key,
            "target": target,
            "status": "unchanged",
            "path": previous.get("last_download_path"),
        }
    except Exception as exc:
        state[key] = {**previous, "last_checked_at": _now_iso(), "error": str(exc)}
        return {"key": key, "target": target, "status": "error", "error": str(exc)}


def run_watch(config_path: Optional[str] = None) -> List[Dict]:
    config, _ = load_config(config_path)
    state = load_state(config["state_file"])
    results = [check_target(target, state) for target in config["targets"]]
    save_state(config["state_file"], state)
    return results


def list_targets(config_path: Optional[str] = None) -> List[Dict]:
    config, _ = load_config(config_path)
    state = load_state(config["state_file"])
    rows = []
    for target in config["targets"]:
        key = target_key(target)
        rows.append({"key": key, "target": target, "state": state.get(key, {})})
    return rows


def _validate_time(value: str) -> Tuple[int, int]:
    try:
        hour_str, minute_str = value.split(":", 1)
        hour = int(hour_str)
        minute = int(minute_str)
    except ValueError as exc:
        raise ValueError("--time must use HH:MM format") from exc
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("--time must be a valid 24-hour time")
    return hour, minute


def build_cron_expression(every: str, time_value: str, weekday: str = "mon") -> str:
    hour, minute = _validate_time(time_value)
    if every == "day":
        return f"{minute} {hour} * * *"
    if every == "week":
        weekday_num = WEEKDAYS.get(weekday.lower())
        if weekday_num is None:
            raise ValueError("--weekday must be one of: sun, mon, tue, wed, thu, fri, sat")
        return f"{minute} {hour} * * {weekday_num}"
    raise ValueError("--every must be one of: day, week")


def _marker(config_path: str) -> str:
    return f"{MARKER_PREFIX}{_expand_path(config_path)}"


def _read_crontab() -> List[str]:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return result.stdout.splitlines()


def _write_crontab(lines: List[str]) -> None:
    payload = "\n".join(lines).rstrip()
    if payload:
        payload += "\n"
    result = subprocess.run(["crontab", "-"], input=payload, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Failed to update crontab")


def _without_marker(lines: List[str], marker: str) -> List[str]:
    cleaned = []
    skip_next = False
    for line in lines:
        if skip_next:
            skip_next = False
            continue
        if line == marker:
            skip_next = True
            continue
        cleaned.append(line)
    return cleaned


def _log_file_for_config(config_path: str) -> str:
    config_dir = os.path.dirname(_expand_path(config_path))
    return os.path.join(config_dir, "watch.log") if config_dir else DEFAULT_LOG_FILE


def build_cron_command(config_path: str) -> str:
    config = _expand_path(config_path)
    log_file = _log_file_for_config(config)
    _ensure_parent(log_file)
    return f"modely-ai watch run --config {shlex.quote(config)} >> {shlex.quote(log_file)} 2>&1"


def install_crontab(config_path: Optional[str], every: str, time_value: str, weekday: str = "mon") -> str:
    if os.name == "nt":
        raise RuntimeError("watch install uses crontab and is not supported on Windows")
    config = _expand_path(config_path or DEFAULT_CONFIG_FILE)
    expression = build_cron_expression(every, time_value, weekday)
    marker = _marker(config)
    lines = _without_marker(_read_crontab(), marker)
    lines.extend([marker, f"{expression} {build_cron_command(config)}"])
    _write_crontab(lines)
    return f"{expression} {build_cron_command(config)}"


def uninstall_crontab(config_path: Optional[str]) -> bool:
    if os.name == "nt":
        raise RuntimeError("watch uninstall uses crontab and is not supported on Windows")
    config = _expand_path(config_path or DEFAULT_CONFIG_FILE)
    marker = _marker(config)
    lines = _read_crontab()
    cleaned = _without_marker(lines, marker)
    changed = cleaned != lines
    if changed:
        _write_crontab(cleaned)
    return changed


def crontab_status(config_path: Optional[str]) -> Optional[str]:
    config = _expand_path(config_path or DEFAULT_CONFIG_FILE)
    marker = _marker(config)
    lines = _read_crontab()
    for index, line in enumerate(lines):
        if line == marker and index + 1 < len(lines):
            return lines[index + 1]
    return None


def _print_run_results(results: List[Dict]) -> None:
    if not results:
        print("No watch targets configured.")
        return
    for result in results:
        if result["status"] == "downloaded":
            print(f"downloaded {result['key']} -> {result.get('path')}")
        elif result["status"] == "unchanged":
            print(f"unchanged {result['key']}")
        else:
            print(f"error {result['key']}: {result.get('error')}")

    print()
    print("Watched resources:")
    for result in results:
        target = result.get("target") or _target_from_key(result["key"])
        status = "complete" if result["status"] in {"downloaded", "unchanged"} else "failed"
        path = result.get("path") or "-"
        print(
            f"  [{status}] {target['source']} {target['repo_type']} "
            f"{target['repo_id']} ({target['revision']}) -> {path}"
        )

    if all(result["status"] in {"downloaded", "unchanged"} for result in results):
        print("All watched resources are downloaded.")
    else:
        print("Some watched resources failed to download.")


def _target_from_key(key: str) -> Dict:
    source, repo_type, repo_id, revision = key.split(":", 3)
    return {
        "source": source,
        "repo_type": repo_type,
        "repo_id": repo_id,
        "revision": revision,
    }


def _print_list(rows: List[Dict]) -> None:
    if not rows:
        print("No watch targets configured.")
        return
    for row in rows:
        state = row["state"]
        print(f"\n{row['key']}")
        print(f"  download: {row['target']['download']}")
        print(f"  last checked: {state.get('last_checked_at', '-')}")
        print(f"  last downloaded: {state.get('last_downloaded_at', '-')}")
        if state.get("last_download_path"):
            print(f"  path: {state['last_download_path']}")
        if state.get("error"):
            print(f"  error: {state['error']}")


def configure_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    subparsers = parser.add_subparsers(dest="watch_command", help="Watch commands")

    init_parser = subparsers.add_parser("init", help="Create a watch config template")
    init_parser.add_argument("--config", default=None, help="Path to watch config")
    init_parser.add_argument("--force", action="store_true", help="Overwrite an existing config")

    run_parser = subparsers.add_parser("run", help="Check once and download changed targets")
    run_parser.add_argument("--config", default=None, help="Path to watch config")

    list_parser = subparsers.add_parser("list", help="List watch targets and state")
    list_parser.add_argument("--config", default=None, help="Path to watch config")

    install_parser = subparsers.add_parser("install", help="Install a crontab entry")
    install_parser.add_argument("--config", default=None, help="Path to watch config")
    install_parser.add_argument("--every", choices=["day", "week"], required=True, help="Run daily or weekly")
    install_parser.add_argument("--time", required=True, help="Run time in HH:MM format")
    install_parser.add_argument("--weekday", default="mon", help="Weekday for weekly runs")

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove the crontab entry")
    uninstall_parser.add_argument("--config", default=None, help="Path to watch config")

    status_parser = subparsers.add_parser("status", help="Show the installed crontab entry")
    status_parser.add_argument("--config", default=None, help="Path to watch config")
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="modely-ai watch", description="Watch repositories and download updates")
    return configure_parser(parser)


def main(args=None) -> None:
    if isinstance(args, argparse.Namespace):
        parsed = args
    else:
        parser = build_parser()
        parsed = parser.parse_args(args)

    command = getattr(parsed, "watch_command", None)
    try:
        if command == "init":
            path = init_config(parsed.config, force=parsed.force)
            print(f"Watch config created: {path}")
        elif command == "run":
            _print_run_results(run_watch(parsed.config))
        elif command == "list":
            _print_list(list_targets(parsed.config))
        elif command == "install":
            entry = install_crontab(parsed.config, parsed.every, parsed.time, parsed.weekday)
            print(f"Installed watch cron: {entry}")
        elif command == "uninstall":
            removed = uninstall_crontab(parsed.config)
            print("Removed watch cron." if removed else "No watch cron found.")
        elif command == "status":
            entry = crontab_status(parsed.config)
            print(entry if entry else "No watch cron installed.")
        else:
            build_parser().print_help()
            sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
