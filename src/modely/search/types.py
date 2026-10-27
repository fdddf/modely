"""Shared types for modely-ai search module."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SearchResult:
    """Unified search result across all platforms."""

    id: str
    source: str  # "hf" or "ms"
    repo_type: str  # "model" or "dataset"
    url: str = ""  # Web page URL for the model/dataset
    author: Optional[str] = None
    downloads: int = 0
    likes: int = 0
    last_modified: Optional[str] = None  # ISO 8601
    created_at: Optional[str] = None
    pipeline_tag: Optional[str] = None  # task type
    library_name: Optional[str] = None  # HF only
    tags: List[str] = field(default_factory=list)
    license: Optional[str] = None
    description: Optional[str] = None
