import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from .search import find_files

USER_HOME = Path.home()

EXTENSION_CATEGORIES = {
    "Documents": [".pdf", ".docx", ".doc", ".txt", ".pptx", ".ppt", ".xlsx", ".xls", ".csv", ".rtf", ".epub", ".odt"],
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico", ".tiff", ".raw"],
    "Installers": [".exe", ".msi", ".bat", ".cmd", ".iso", ".appx"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
    "Code": [".py", ".js", ".ts", ".html", ".css", ".json", ".sql", ".sh", ".c", ".cpp", ".java", ".xml", ".yaml", ".yml"],
    "Media": [".mp3", ".wav", ".mp4", ".mkv", ".mov", ".avi", ".flac", ".ogg", ".webm"],
}

def resolve_target_dir(name: str) -> Optional[Path]:
    """Resolve keywords like 'downloads', 'documents', 'desktop' to Path."""
    clean = name.strip().lower()
    mapping = {
        "download": USER_HOME / "Downloads",
        "downloads": USER_HOME / "Downloads",
        "document": USER_HOME / "Documents",
        "documents": USER_HOME / "Documents",
        "desktop": USER_HOME / "Desktop",
        "pictures": USER_HOME / "Pictures",
        "music": USER_HOME / "Music",
        "videos": USER_HOME / "Videos",
    }
    for key, path in mapping.items():
        if key in clean and path.exists():
            return path
    
    # Try as direct path
    direct = Path(name).resolve()
    if direct.is_dir():
        return direct

    return None

def rename_file(target: str, new_name: str) -> Dict[str, Any]:
    """
    Rename a file. Target can be an absolute path or a filename to search.
    Preserves original extension if omitted in new_name.
    """
    clean_new_name = new_name.strip()
    target_path = Path(target)

    # If target is not an existing file, search for it
    if not target_path.is_file():
        search_res = find_files(target, max_results=1)
        if not search_res["matches"]:
            return {
                "ok": False,
                "error": f"Could not find any file matching '{target}' to rename."
            }
        target_path = Path(search_res["matches"][0]["path"])

    # Ensure extension is preserved if new_name didn't specify one
    orig_ext = target_path.suffix
    if not Path(clean_new_name).suffix and orig_ext:
        clean_new_name += orig_ext

    dest_path = target_path.parent / clean_new_name

    if dest_path.exists() and dest_path != target_path:
        return {
            "ok": False,
            "error": f"A file named '{clean_new_name}' already exists in {target_path.parent}."
        }

    try:
        target_path.rename(dest_path)
        return {
            "ok": True,
            "old_name": target_path.name,
            "new_name": dest_path.name,
            "folder": str(dest_path.parent),
            "new_path": str(dest_path),
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"Failed to rename file: {str(e)}"
        }

def organize_directory(target: str = "downloads") -> Dict[str, Any]:
    """
    Organize loose files in a directory into clean subfolders by category.
    Does not recurse into existing subdirectories to avoid disturbing sorted trees.
    """
    dir_path = resolve_target_dir(target)
    if not dir_path or not dir_path.is_dir():
        return {
            "ok": False,
            "error": f"Directory '{target}' could not be located or is invalid."
        }

    category_map = {}
    for cat, exts in EXTENSION_CATEGORIES.items():
        for ext in exts:
            category_map[ext.lower()] = cat

    stats = {cat: 0 for cat in EXTENSION_CATEGORIES}
    moved_files = []

    try:
        for entry in os.scandir(dir_path):
            if not entry.is_file(follow_symlinks=False):
                continue

            file_path = Path(entry.path)
            ext = file_path.suffix.lower()
            category = category_map.get(ext, "Other")

            dest_folder = dir_path / category
            dest_folder.mkdir(exist_ok=True)

            dest_file = dest_folder / file_path.name
            # If destination already exists with same name, find unique name
            counter = 1
            while dest_file.exists():
                dest_file = dest_folder / f"{file_path.stem} ({counter}){file_path.suffix}"
                counter += 1

            shutil.move(str(file_path), str(dest_file))
            if category in stats:
                stats[category] += 1
            else:
                stats["Other"] = stats.get("Other", 0) + 1

            moved_files.append({"from": file_path.name, "to": str(dest_file.relative_to(dir_path))})

        total_moved = len(moved_files)
        active_cats = {k: v for k, v in stats.items() if v > 0}

        return {
            "ok": True,
            "folder": str(dir_path),
            "folder_name": dir_path.name,
            "total_moved": total_moved,
            "breakdown": active_cats,
            "details": moved_files[:15],
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"Failed to organize directory: {str(e)}"
        }
