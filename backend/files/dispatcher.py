import re
from typing import Dict, Any, Optional
from .search import find_files, open_in_explorer
from .manage import rename_file, organize_directory
from .summarize import summarize_document

COMMON_EXTENSIONS = {
    'py', 'jpeg', 'jpg', 'png', 'gif', 'bmp', 'webp', 'svg',
    'pdf', 'docx', 'doc', 'txt', 'csv', 'xlsx', 'xls', 'pptx', 'ppt',
    'zip', 'rar', '7z', 'tar', 'gz',
    'mp3', 'wav', 'mp4', 'mkv', 'avi', 'mov',
    'json', 'xml', 'yaml', 'yml', 'toml', 'env',
    'bat', 'cmd', 'ps1', 'sh',
    'exe', 'msi', 'iso',
    'html', 'css', 'js', 'ts', 'jsx', 'tsx', 'rs', 'go', 'cpp', 'c', 'h', 'md', 'log'
}

def extract_file_search_query(text: str) -> Optional[str]:
    """
    Extract file search target from natural speech or text.
    Handles STT quirks, including phonetic mishearings of 'locate' as 'look it' / 'lookit' / 'look at' / 'look for',
    as well as variations like 'find my file, summarize.py' or 'where is file: summarize.py'.
    """
    clean = text.strip()
    if not clean:
        return None

    # Never intercept general informational questions
    if re.match(r"^(what\s+is|what\'s|how\s+to|how\s+do|why\s+is|why\s+do|tell\s+me\s+about|explain)\b", clean, re.IGNORECASE):
        return None

    # Never intercept screen vision commands
    if re.search(r"\b(on\s+(?:the\s+|my\s+)?screen|at\s+(?:the\s+|my\s+)?screen|look\s+at\s+(?:the\s+|my\s+)?screen)\b", clean, re.IGNORECASE):
        return None

    # Speech-to-text normalizations:
    # 1. 'dot py' -> '.py'
    norm = re.sub(r"\s+dot\s+([a-zA-Z0-9]{1,6})\b", r".\1", clean, flags=re.IGNORECASE)
    # 2. Spaces around dot before extension: e.g. 'summarize . py' -> 'summarize.py'
    norm = re.sub(r"([a-zA-Z0-9_\-]+)\s*\.\s*([a-zA-Z0-9]{1,6})\b", r"\1.\2", norm)

    # 3. Strip leading conversational greetings / fillers
    norm = re.sub(r"^(?:alright|okay|ok|hey|hi|hello)?\s*(?:sir|jarvis|assistant|computer)?[\s,:\-]*", "", norm, flags=re.IGNORECASE).strip()
    norm = re.sub(r"^(?:can\s+you|could\s+you|please|i\s+want\s+to|help\s+me|would\s+you)?\s*(?:please)?[\s,:\-]*", "", norm, flags=re.IGNORECASE).strip()

    # Track if user explicitly mentioned 'file' or 'document'
    explicitly_mentioned_file = bool(re.search(r"\b(files?|documents?|docs?)\b", norm, re.IGNORECASE))

    # 4. Check for find/locate/look triggers
    # Triggers include phonetic STT misrecognitions of 'locate': 'look it', 'lookit', 'look at', 'look for', 'lock it', 'locate'
    trigger_pattern = (
        r"^(?P<verb>find|locate|locat|located|look\s*it|lookit|look\s*at|look\s*for|lock\s*it|"
        r"search\s*for|search|where\s+is|where\'s|open\s+(?:up\s+)?(?:the\s+|my\s+)?file|open|"
        r"show\s+me\s+(?:the\s+|my\s+)?file)\b[\s,:\-]*"
    )
    
    m = re.match(trigger_pattern, norm, flags=re.IGNORECASE)
    if not m:
        return None

    verb = m.group("verb").lower()
    remainder = norm[m.end():].strip()
    if not remainder:
        return None

    # Guard against conversational idioms like 'find out...', 'look into...', 'look up...'
    if re.match(r"^(out|into|up|after)\b", remainder, re.IGNORECASE):
        return None

    # Strip trailing polite tokens: 'please', 'for me', 'now', etc.
    remainder = re.sub(r"[\s,:\-]+(?:please|for\s+me|right\s+now|now|immediately)[\.\?!]*$", "", remainder, flags=re.IGNORECASE).strip()

    # 5. Clean leading descriptors like 'my file,', 'the file:', 'file called', 'document'
    # This specifically solves the issue where 'file' or 'my file' remains in the query
    strip_chars = " \t\r\n,:;-\"'"
    prev = None
    while prev != remainder:
        prev = remainder
        remainder = re.sub(r"^(?:the|my|a|this)\s+", "", remainder, flags=re.IGNORECASE).strip(strip_chars)
        remainder = re.sub(r"^(?:files?|documents?|docs?|items?)\b[\s,:\-]*", "", remainder, flags=re.IGNORECASE).strip(strip_chars)
        remainder = re.sub(r"^(?:called|named)\b[\s,:\-]*", "", remainder, flags=re.IGNORECASE).strip(strip_chars)

    # Strip any enclosing quotes and sentence-ending punctuation like periods/question marks
    candidate = remainder.strip(" \t\r\n.?!,;:\"'`")

    # 6. Check if candidate has a recognized file with extension
    # E.g. 'summarize.py' or 'roadmap.jpeg'
    ext_match = re.search(r"([a-zA-Z0-9_\-]+\.([a-zA-Z0-9]{1,6}))", candidate)
    has_ext = False
    if ext_match:
        ext = ext_match.group(2).lower()
        if ext in COMMON_EXTENSIONS:
            has_ext = True
            file_part = ext_match.group(1).strip()
            # Clean any remaining 'file' prefix in the token
            file_part = re.sub(r"^(?:my\s+|the\s+)?(?:files?|documents?|docs?)[\s,:\-]+", "", file_part, flags=re.IGNORECASE).strip()
            if file_part:
                candidate = file_part

    # 7. Disambiguation for ambiguous verbs like 'where is' or 'look at'
    # If the user said "where is Paris?" or "look at the sunset":
    # Unless they mentioned 'file' or specified a file extension, do NOT intercept as file search!
    if any(v in verb for v in ["where is", "where's", "look at"]) and not (explicitly_mentioned_file or has_ext):
        return None

    # 8. Final validation
    if not candidate:
        return None

    # If it's a multi-word phrase with no extension (e.g. 'how beautiful the sky is'), reject
    words = candidate.split()
    if len(words) > 4 and not has_ext:
        return None

    # Filter out question words as standalone candidates
    if candidate.lower() in {"out", "how", "why", "who", "what", "where"}:
        return None

    return candidate

async def handle_file_intent(text: str) -> Optional[Dict[str, Any]]:
    """
    Check if the user request matches a file management action:
    - Find/Search & Open in Explorer (with STT phonetic & comma resilience)
    - Rename File
    - Organize Downloads/Documents
    - Summarize Document
    Returns a dict with action details and reply if matched, or None if regular chat.
    """
    clean = text.strip()
    lower = clean.lower()

    # 1. Organize Command
    # e.g., "organize my downloads", "clean up my documents", "organize desktop"
    organize_match = re.search(r"\b(organize|sort|clean up|tidy up)\s+(?:my\s+)?(downloads?|documents?|desktop|pictures?)\b", lower)
    if organize_match:
        target_dir = organize_match.group(2)
        res = organize_directory(target_dir)
        if res["ok"]:
            breakdown_str = ", ".join(f"{count} {cat}" for cat, count in res["breakdown"].items())
            reply = f"Organized {res['total_moved']} files in your {res['folder_name']} folder ({breakdown_str})."
        else:
            reply = res["error"]
        return {
            "action": "organize",
            "reply": reply,
            "data": res
        }

    # 2. Rename Command
    # e.g., "rename report.pdf to annual_report.pdf", "change name of test.txt to final.txt"
    rename_match = re.search(r"\b(?:rename|change\s+(?:the\s+)?name\s+of)\s+['\"]?(.+?)['\"]?\s+to\s+['\"]?(.+?)['\"]?[\s\.\?!]*$", clean, re.IGNORECASE)
    if rename_match:
        old_name = rename_match.group(1).strip(" \t\r\n.?!,;:\"'`")
        old_name = re.sub(r"^(?:the|my|a|this)\s+", "", old_name, flags=re.IGNORECASE).strip(" \t\r\n.?!,;:\"'`")
        old_name = re.sub(r"^(?:files?|documents?|docs?)\b[\s,:\-]*", "", old_name, flags=re.IGNORECASE).strip(" \t\r\n.?!,;:\"'`")
        new_name = rename_match.group(2).strip(" \t\r\n.?!,;:\"'`")
        new_name = re.sub(r"^(?:the|my|a|this)\s+", "", new_name, flags=re.IGNORECASE).strip(" \t\r\n.?!,;:\"'`")
        new_name = re.sub(r"^(?:files?|documents?|docs?)\b[\s,:\-]*", "", new_name, flags=re.IGNORECASE).strip(" \t\r\n.?!,;:\"'`")
        res = rename_file(old_name, new_name)
        if res["ok"]:
            reply = f"Renamed '{res['old_name']}' to '{res['new_name']}' in {res['folder']}."
        else:
            reply = res["error"]
        return {
            "action": "rename",
            "reply": reply,
            "data": res
        }

    # 3. Summarize Command
    # e.g., "summarize invoice.pdf", "give me a summary of resume.docx", "summarize my notes.txt"
    summarize_match = re.search(
        r"\b(?:summarize|give\s+me\s+a\s+summary\s+of|tldr|tl;dr)\s+(?:my\s+|the\s+)?(?:files?|documents?|docs?)?[\s,:\-]*['\"]?([a-zA-Z0-9_\-\.\s]+\.[a-zA-Z0-9]+)['\"]?[\s\.\?!]*",
        clean,
        re.IGNORECASE
    )
    if summarize_match:
        target_doc = summarize_match.group(1).strip(" \t\r\n.?!,;:\"'`")
        target_doc = re.sub(r"^(?:my\s+|the\s+)?(?:files?|documents?|docs?)[\s,:\-]+", "", target_doc, flags=re.IGNORECASE).strip(" \t\r\n.?!,;:\"'`")
        res = await summarize_document(target_doc)
        if res["ok"]:
            reply = f"Here is a summary of {res['filename']}:\n\n{res['summary']}"
        else:
            reply = res["error"]
        return {
            "action": "summarize",
            "reply": reply,
            "data": res
        }

    # 4. Find / Locate / Look for / Open File Command
    query = extract_file_search_query(clean)
    if query:
        search_res = find_files(query, max_results=10)
        matches = search_res["matches"]
        total = search_res["total"]

        if not matches:
            reply = f"I couldn't find any file matching '{query}' in your user folders."
            return {
                "action": "find_files",
                "reply": reply,
                "data": search_res,
            }

        # Automatically reveal the most recent match in File Explorer
        top_match = matches[0]
        open_in_explorer(top_match["path"])

        if total == 1:
            reply = f"Found '{top_match['name']}' in {top_match['folder']}. Opening it in File Explorer."
        else:
            reply = (
                f"Found {total} files matching '{query}'. Opening the most recent one in {top_match['folder']} "
                f"({top_match['modified']}). You can pick other matches on screen."
            )

        return {
            "action": "find_files",
            "reply": reply,
            "data": search_res,
        }

    return None
