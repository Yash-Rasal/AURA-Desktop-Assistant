from pathlib import Path
from typing import Dict, Any
from vision import ollama_client
from .search import find_files

def extract_file_text(file_path: Path, max_chars: int = 6000) -> str:
    """Extract clean text content from PDF, DOCX, TXT, MD, CSV, etc."""
    ext = file_path.suffix.lower()

    if ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            text_parts = []
            char_count = 0
            for page in reader.pages:
                t = page.extract_text() or ""
                text_parts.append(t)
                char_count += len(t)
                if char_count >= max_chars:
                    break
            return "\n".join(text_parts)[:max_chars].strip()
        except Exception as e:
            raise RuntimeError(f"Could not read PDF: {e}")

    elif ext in [".docx", ".doc"]:
        try:
            import docx
            doc = docx.Document(str(file_path))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            return text[:max_chars].strip()
        except Exception as e:
            raise RuntimeError(f"Could not read DOCX: {e}")

    else:
        # Plain text, markdown, csv, json, code
        for enc in ["utf-8", "utf-8-sig", "cp1252", "latin-1"]:
            try:
                with open(file_path, "r", encoding=enc, errors="ignore") as f:
                    return f.read(max_chars).strip()
            except Exception:
                continue

    return ""

async def summarize_document(target: str) -> Dict[str, Any]:
    """
    Locates document, extracts text, and queries Ollama to generate an executive summary.
    """
    target_path = Path(target)
    if not target_path.is_file():
        search_res = find_files(target, max_results=1)
        if not search_res["matches"]:
            return {
                "ok": False,
                "error": f"Could not find any document matching '{target}' to summarize."
            }
        target_path = Path(search_res["matches"][0]["path"])

    try:
        text = extract_file_text(target_path)
        if not text:
            return {
                "ok": False,
                "error": f"Document '{target_path.name}' is empty or contains no readable text."
            }

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an executive assistant. Summarize the provided document in exactly "
                    "3 short bullet points, followed by a 1-sentence bottom line. Keep it concise."
                ),
            },
            {
                "role": "user",
                "content": f"Document Name: {target_path.name}\n\nContent:\n{text}",
            },
        ]

        summary = await ollama_client.chat(messages)
        return {
            "ok": True,
            "filename": target_path.name,
            "path": str(target_path),
            "summary": summary,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"Failed to summarize '{target_path.name}': {str(e)}"
        }
