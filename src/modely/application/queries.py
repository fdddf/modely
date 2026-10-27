"""Query-oriented application services.

These functions coordinate existing domain modules and return values for callers
to present. They do not print or terminate the process.
"""

from __future__ import annotations

from ..files import filter_files, list_repo_files
from ..info import get_repo_info, resolve_repo_ref
from ..plan import create_download_plan
from .download_profiles import resolve_download_profile
from ..uri import parse_modely_uri


def get_info(resource: str, *, source: str = "auto", repo_type: str = "auto", revision=None, token=None, endpoint=None):
    return get_repo_info(resource, revision=revision, token=token, endpoint=endpoint, source=source, repo_type=repo_type)


def get_files(
    resource: str,
    *,
    source: str = "auto",
    repo_type: str = "auto",
    revision=None,
    token=None,
    endpoint=None,
    release=None,
    include=None,
    exclude=None,
    profile=None,
):
    include, exclude = resolve_download_profile(profile, include, exclude)
    if release:
        ref = parse_modely_uri(resource, source=source, repo_type=repo_type)
    else:
        ref = resolve_repo_ref(resource, revision=revision, token=token, endpoint=endpoint, source=source, repo_type=repo_type)
    files = list_repo_files(ref, revision=revision, token=token, endpoint=endpoint, release=release)
    return ref, filter_files(files, include, exclude)


def get_download_plan(
    resource: str,
    *,
    source: str = "auto",
    repo_type: str = "auto",
    revision=None,
    include=None,
    exclude=None,
    profile=None,
    token=None,
    endpoint=None,
    cache_dir=None,
    local_dir=None,
    release=None,
):
    return create_download_plan(
        resource,
        source=source,
        repo_type=repo_type,
        revision=revision,
        include=include,
        exclude=exclude,
        profile=profile,
        token=token,
        endpoint=endpoint,
        cache_dir=cache_dir,
        local_dir=local_dir,
        release=release,
    )
