"""File discovery and management utilities"""
from pathlib import Path
from typing import List, Dict


def match_union(directory: Path, pattern: str) -> List[Path]:
    """Match files using union of glob patterns separated by |"""
    pats = [p.strip() for p in (pattern or "").split("|") if p.strip()]
    if not pats:
        pats = ["*.mp4"]
    seen: Dict[Path, Path] = {}
    for pat in pats:
        for p in directory.glob(pat):
            if p.is_file():
                seen[p.resolve()] = p
    return sorted(seen.values())


def discover_files(directory: Path, pattern: str) -> List[Path]:
    """Discover media files in directory using pattern"""
    return match_union(directory, pattern)