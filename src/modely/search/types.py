"""Shared types for modely-ai search module."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SearchResult:
    """Unified search result across all platforms."""

    id: str
    source: str
    repo_type: str
    url: str = ""
    author: Optional[str] = None
    downloads: int = 0
    likes: int = 0
    last_modified: Optional[str] = None
    created_at: Optional[str] = None
    pipeline_tag: Optional[str] = None
    library_name: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    license: Optional[str] = None
    description: Optional[str] = None
    name: Optional[str] = None
    summary: Optional[str] = None
    score: Optional[float] = None
    size_bytes: int = 0
    stars: int = 0
    forks: int = 0
    modely_uri: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.name is None:
            self.name = self.id.rsplit("/", 1)[-1] if self.id else None
        if self.summary is None:
            self.summary = self.description
        if not self.stars:
            self.stars = self.likes or 0
        if self.modely_uri is None:
            self.modely_uri = _format_modely_uri(self.source, self.repo_type, self.id)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-ready dictionary with the stable search schema."""
        return asdict(self)


def _format_modely_uri(source: str, repo_type: str, repo_id: str) -> Optional[str]:
    if not source or not repo_id:
        return None
    if source == "hf":
        segment = "datasets" if repo_type == "dataset" else "models" if repo_type == "model" else repo_type
        return f"hf://{segment}/{repo_id}"
    if source == "ms":
        segment = "datasets" if repo_type == "dataset" else "models" if repo_type == "model" else repo_type
        return f"ms://{segment}/{repo_id}"
    if source == "github":
        return f"github://{repo_id}"
    if source == "kaggle":
        segment = "competitions" if repo_type == "competition" else "datasets"
        return f"kaggle://{segment}/{repo_id}"
    return None
