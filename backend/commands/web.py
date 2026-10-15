from __future__ import annotations

import re
import urllib.parse
import webbrowser
from typing import Any, Dict, Optional

KNOWN_SITES: Dict[str, Dict[str, str]] = {
    "youtube": {"title": "YouTube", "url": "https://www.youtube.com"},
    "google": {"title": "Google", "url": "https://www.google.com"},
    "github": {"title": "GitHub", "url": "https://www.github.com"},
    "reddit": {"title": "Reddit", "url": "https://www.reddit.com"},
    "twitter": {"title": "X (Twitter)", "url": "https://x.com"},
    "x": {"title": "X", "url": "https://x.com"},
    "chatgpt": {"title": "ChatGPT", "url": "https://chatgpt.com"},
    "openai": {"title": "OpenAI", "url": "https://chatgpt.com"},
    "claude": {"title": "Claude", "url": "https://claude.ai"},
    "gmail": {"title": "Gmail", "url": "https://mail.google.com"},
    "email": {"title": "Gmail", "url": "https://mail.google.com"},
    "mail": {"title": "Gmail", "url": "https://mail.google.com"},
    "google mail": {"title": "Gmail", "url": "https://mail.google.com"},
    "netflix": {"title": "Netflix", "url": "https://www.netflix.com"},
    "amazon": {"title": "Amazon", "url": "https://www.amazon.com"},
    "linkedin": {"title": "LinkedIn", "url": "https://www.linkedin.com"},
    "wikipedia": {"title": "Wikipedia", "url": "https://www.wikipedia.org"},
    "twitch": {"title": "Twitch", "url": "https://www.twitch.tv"},
    "spotify": {"title": "Spotify Web", "url": "https://open.spotify.com"},
    "whatsapp": {"title": "WhatsApp Web", "url": "https://web.whatsapp.com"},
    "instagram": {"title": "Instagram", "url": "https://www.instagram.com"},
    "facebook": {"title": "Facebook", "url": "https://www.facebook.com"},
    "stackoverflow": {"title": "Stack Overflow", "url": "https://stackoverflow.com"},
    "stack overflow": {"title": "Stack Overflow", "url": "https://stackoverflow.com"},
    "notion": {"title": "Notion", "url": "https://www.notion.so"},
    "discord": {"title": "Discord Web", "url": "https://discord.com/app"},
    "huggingface": {"title": "Hugging Face", "url": "https://huggingface.co"},
}

TLD_PATTERN = re.compile(
    r"^(?:https?:\/\/)?([a-zA-Z0-9\-]+\.(?:com|org|net|io|dev|ai|edu|gov|in|co|app|tech|me|tv|xyz|info))(?:[\/\?#].*)?$",
    re.IGNORECASE,
)


def resolve_web_target(query: str) -> Optional[Dict[str, str]]:
    """
    Resolve a web query to a URL and display title.
    Handles:
    - Known site keywords (e.g. 'youtube', 'github')
    - Direct URLs or domains ('https://...', 'reddit.com', 'espn.com')
    - Search requests ('search for x on google', 'google x')
    """
    clean = query.strip()
    lower = clean.lower()

    # 1. Search queries
    # e.g., "search google for python", "search on youtube for chill music", "google latest news"
    search_yt = re.search(
        r"^(?:search\s+(?:for\s+)?|find\s+)?(.+?)\s+(?:on\s+youtube|in\s+youtube)$",
        clean,
        re.IGNORECASE,
    ) or re.search(
        r"^(?:search\s+youtube\s+(?:for\s+)?)(.+)$",
        clean,
        re.IGNORECASE,
    )
    if search_yt:
        search_term = search_yt.group(1).strip()
        encoded = urllib.parse.quote(search_term)
        return {
            "title": f"YouTube search for '{search_term}'",
            "url": f"https://www.youtube.com/results?search_query={encoded}",
            "is_search": True,
        }

    search_google = re.search(
        r"^(?:search\s+google\s+(?:for\s+)?|google\s+)(.+)$",
        clean,
        re.IGNORECASE,
    ) or re.search(
        r"^(?:search\s+(?:for\s+)?|find\s+)?(.+?)\s+(?:on\s+google|in\s+google)$",
        clean,
        re.IGNORECASE,
    )
    if search_google:
        search_term = search_google.group(1).strip()
        encoded = urllib.parse.quote(search_term)
        return {
            "title": f"Google search for '{search_term}'",
            "url": f"https://www.google.com/search?q={encoded}",
            "is_search": True,
        }

    # 2. Known sites dictionary
    # Strip common prefixes like 'the', 'website', 'page'
    site_key = re.sub(r"^(?:the\s+)?(?:website\s+|site\s+|page\s+)?", "", lower).strip()
    if site_key in KNOWN_SITES:
        return {
            "title": KNOWN_SITES[site_key]["title"],
            "url": KNOWN_SITES[site_key]["url"],
            "is_search": False,
        }

    # 3. Direct domain or URL pattern
    m = TLD_PATTERN.match(clean)
    if m:
        url = clean if clean.startswith("http://") or clean.startswith("https://") else f"https://{clean}"
        domain = m.group(1)
        return {
            "title": domain,
            "url": url,
            "is_search": False,
        }

    return None


def launch_website(query: str) -> Dict[str, Any]:
    """
    Launch website or search in user's default browser.
    Returns status dict and conversational reply.
    """
    target = resolve_web_target(query)
    if not target:
        return {
            "ok": False,
            "query": query,
            "error": f"Could not determine website URL for '{query}'.",
            "reply": f"I couldn't identify the website for '{query}'.",
        }

    url = target["url"]
    title = target["title"]

    try:
        webbrowser.open(url)
        if target.get("is_search"):
            reply = f"Searching for '{query}' in your browser."
        else:
            reply = f"Opening {title} in your browser."

        return {
            "ok": True,
            "title": title,
            "url": url,
            "reply": reply,
        }
    except Exception as e:
        return {
            "ok": False,
            "title": title,
            "url": url,
            "error": str(e),
            "reply": f"Failed to open {title}: {str(e)}",
        }
