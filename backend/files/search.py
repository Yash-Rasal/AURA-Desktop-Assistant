import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Primary user directories to search for sub-second responses
USER_HOME = Path.home()
PRIMARY_SCOPES = [
    USER_HOME / "Downloads",
    USER_HOME / "Desktop",
    USER_HOME / "Documents",
    USER_HOME / "Projects",
    USER_HOME / "Pictures",
    USER_HOME / "Videos",
    USER_HOME / "Music",
    USER_HOME / "OneDrive" / "Desktop",
    USER_HOME / "OneDrive" / "Documents",
    USER_HOME / "OneDrive" / "Pictures",
    USER_HOME / "OneDrive",
]

# Folders to skip for speed and security
IGNORED_DIRS = {
    ".git",
    "node_modules",
    "appdata",
    "__pycache__",
    "venv",
    ".venv",
    "$recycle.bin",
    "system volume information",
    ".antigravity-ide",
    ".vscode",
    ".cache",
}

def human_readable_size(size_bytes: int) -> str:
    """Format bytes into KB, MB, GB."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def _scan_directory(dir_path: Path, query_lower: str, max_depth: int = 4, current_depth: int = 0) -> List[Dict[str, Any]]:
    matches = []
    if current_depth > max_depth or not dir_path.exists():
        return matches

    query_stem = Path(query_lower).stem
    query_ext = Path(query_lower).suffix.lower()
    ext_equivalent = {".jpg": ".jpeg", ".jpeg": ".jpg"}
    alt_ext = ext_equivalent.get(query_ext, query_ext)
    alt_query = f"{query_stem}{alt_ext}" if query_ext else query_lower

    try:
        with os.scandir(dir_path) as entries:
            for entry in entries:
                try:
                    name_lower = entry.name.lower()
                    if entry.is_dir(follow_symlinks=False):
                        if name_lower in IGNORED_DIRS or name_lower.startswith("."):
                            continue
                        matches.extend(
                            _scan_directory(Path(entry.path), query_lower, max_depth, current_depth + 1)
                        )
                    elif entry.is_file(follow_symlinks=False):
                        entry_stem = Path(name_lower).stem
                        is_match = (
                            query_lower in name_lower 
                            or alt_query in name_lower 
                            or (len(query_stem) >= 3 and query_stem in entry_stem)
                        )
                        if is_match:
                            stat = entry.stat()
                            is_exact = (
                                name_lower == query_lower
                                or name_lower == alt_query
                                or entry_stem == query_stem
                                or entry_stem == query_lower
                            )
                            matches.append({
                                "name": entry.name,
                                "path": entry.path,
                                "folder": str(dir_path),
                                "size": human_readable_size(stat.st_size),
                                "size_bytes": stat.st_size,
                                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%b %d, %Y, %I:%M %p"),
                                "mtime": stat.st_mtime,
                                "extension": Path(entry.name).suffix.lower(),
                                "is_exact": is_exact,
                            })
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError):
        pass

    return matches

def find_files(query: str, max_results: int = 20, deep_search: bool = False) -> Dict[str, Any]:
    """
    Search for files matching query across user scopes.
    Returns sorted list with exact matches and most recent modified first.
    """
    clean_query = query.strip(" \t\r\n.?!,;:\"'`").lower()
    # Strip any leading 'my file,', 'the file', 'file' that could have leaked
    clean_query = re.sub(
        r"^(?:my\s+|the\s+|a\s+|this\s+)?(?:files?|documents?|docs?)[\s,:\-]+",
        "",
        clean_query,
        flags=re.IGNORECASE,
    ).strip(" \t\r\n.?!,;:\"'`")
    if not clean_query:
        return {"query": query, "total": 0, "matches": []}

    all_matches: List[Dict[str, Any]] = []
    seen_paths = set()

    # 1. Search primary user scopes (sub-second)
    for scope in PRIMARY_SCOPES:
        if scope.exists():
            for m in _scan_directory(scope, clean_query, max_depth=4):
                if m["path"] not in seen_paths:
                    seen_paths.add(m["path"])
                    all_matches.append(m)

    # 2. If nothing found in primary scopes and deep_search is enabled (or fallback)
    if not all_matches and deep_search:
        # Search user profile root with shallow depth
        for m in _scan_directory(USER_HOME, clean_query, max_depth=2):
            if m["path"] not in seen_paths:
                seen_paths.add(m["path"])
                all_matches.append(m)

    # Sort results: exact filename matches first, then latest modified time
    all_matches.sort(key=lambda x: (not x["is_exact"], -x["mtime"]))

    return {
        "query": clean_query,
        "total": len(all_matches),
        "matches": all_matches[:max_results],
    }

def open_in_explorer(file_path: str) -> bool:
    """Open Windows File Explorer and highlight/select the target file."""
    p = Path(file_path).resolve()
    if not p.exists():
        return False

    try:
        # explorer.exe /select,"<path>" highlights the file in its folder
        subprocess.Popen(["explorer.exe", f"/select,{str(p)}"])
        return True
    except Exception as e:
        print(f"[FileManager] Error opening explorer: {e}")
        return False

def open_file(file_path: str) -> bool:
    """Launch the file using default associated application in Windows."""
    p = Path(file_path).resolve()
    if not p.exists():
        return False

    try:
        os.startfile(str(p))
        return True
    except Exception as e:
        print(f"[FileManager] Error launching file: {e}")
        return False
