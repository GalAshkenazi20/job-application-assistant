#!/usr/bin/env python3
"""
Ingest everything the candidate drops into the inbox: old resumes, project write-ups, certificates,
transcripts, recommendation letters, job ads... Extracts the text so Claude can read it and update
resume_data/master_resume.md. Original files are never modified, moved or deleted.

Usage (from the workspace folder):
  python3 tools/ingest.py                 # process new / changed files in ./inbox
  python3 tools/ingest.py path/to/folder  # another folder
  python3 tools/ingest.py --all           # re-process everything

Output:
  inbox/_extracted/<file>.txt     extracted text (one per source file)
  inbox/_extracted/manifest.json  what was processed, its fingerprint and a type guess
  a summary table on stdout:  file | type guess | status | characters

Supported: .pdf (pdftotext, falls back to pypdf), .docx, .txt, .md, .html, .rtf (basic), .json, .csv.
Images (.png .jpg .jpeg .webp .heic) and scanned PDFs are listed as "needs-vision": Claude should
open them directly (e.g. a certificate photo) and read them.
"""
import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
TEXT_EXT = {".txt", ".md", ".markdown", ".json", ".csv"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".gif", ".bmp", ".tif", ".tiff"}

TYPE_HINTS = [
    ("recommendation", r"recommend|to whom it may concern|reference letter|ממליץ|המלצה|לכל המעוניין"),
    ("certificate", r"certificat|certify|certified|completion|has successfully|credential|diploma|תעודה|הסמכה|אישור השתתפות|סיים בהצלחה"),
    ("transcript", r"transcript|\bgpa\b|grade point|grades|semester|גיליון ציונים|ממוצע|ציון|נקודות זכות"),
    ("job-posting", r"requirements|responsibilities|we are looking for|what you'll do|apply now|דרישות התפקיד|תיאור המשרה"),
    ("resume", r"experience|education|skills|projects|curriculum vitae|ניסיון|השכלה|כישורים|קורות חיים"),
    ("project", r"readme|installation|architecture|usage|api|project|repository|פרויקט"),
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def pdf_text(path):
    if shutil.which("pdftotext"):
        r = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout
    try:
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
    except Exception:
        return ""


def docx_text(path):
    """Paragraphs and table cells from word/document.xml - no python-docx needed."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    xml = re.sub(r"</w:tc>", " | ", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    return html.unescape(re.sub(r"\n{3,}", "\n\n", text))


def html_text(raw):
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>|</div>", "\n", raw)
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))


def rtf_text(raw):
    raw = re.sub(r"\\'[0-9a-f]{2}", " ", raw)
    raw = re.sub(r"\\[a-z]+-?\d* ?|[{}]", "", raw)
    return raw


def extract(path):
    ext = path.suffix.lower()
    if ext in IMAGE_EXT:
        return None, "needs-vision"
    try:
        if ext == ".pdf":
            text = pdf_text(path)
            return (text, "ok") if len(text.strip()) > 40 else (None, "needs-vision")  # scanned PDF
        if ext == ".docx":
            return docx_text(path), "ok"
        if ext in TEXT_EXT:
            return path.read_text(encoding="utf-8", errors="replace"), "ok"
        if ext in {".html", ".htm"}:
            return html_text(path.read_text(encoding="utf-8", errors="replace")), "ok"
        if ext == ".rtf":
            return rtf_text(path.read_text(encoding="utf-8", errors="replace")), "ok"
    except Exception as e:  # corrupt / password-protected file
        return None, f"error: {e.__class__.__name__}"
    return None, "unsupported"


def guess_type(name, text):
    hay = (name + " " + (text or "")[:4000]).lower()
    scores = {t: len(re.findall(p, hay, flags=re.I)) for t, p in TYPE_HINTS}
    best = max(scores, key=scores.get)
    return best if scores[best] else "other"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inbox", nargs="?", default="inbox")
    ap.add_argument("--all", action="store_true", help="re-process files that were already processed")
    ap.add_argument("--done", nargs="+", metavar="FILE",
                    help="mark these inbox files as incorporated into the master resume, then exit")
    a = ap.parse_args()

    inbox = Path(a.inbox)
    if not inbox.is_dir():
        sys.exit(f"Folder not found: {inbox}")
    out_dir = inbox / "_extracted"
    out_dir.mkdir(exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    if a.done:
        for rel in a.done:
            rel = str(Path(rel)).replace(str(inbox) + "/", "", 1)
            if rel in manifest:
                manifest[rel]["incorporated"] = True
                print(f"marked as incorporated: {rel}")
            else:
                print(f"not in manifest (run ingest first): {rel}")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    rows = []
    files = sorted(p for p in inbox.rglob("*")
                   if p.is_file() and "_extracted" not in p.parts and "whatsapp" not in p.parts
                   and not p.name.startswith((".", "~$"))
                   and p.name.lower() not in {"readme.md", "desktop.ini", "thumbs.db"})
    for p in files:
        rel = str(p.relative_to(inbox))
        digest = sha256(p)
        prev = manifest.get(rel)
        if prev and prev.get("sha256") == digest and not a.all:
            rows.append((rel, prev.get("type", "?"), "unchanged", prev.get("chars", 0)))
            continue
        text, status = extract(p)
        entry = {"sha256": digest, "size": p.stat().st_size, "status": status,
                 "processed_at": datetime.now().isoformat(timespec="seconds")}
        if text is not None:
            text = re.sub(r"[ \t]+\n", "\n", text).strip()
            out_file = out_dir / (re.sub(r"[\\/]", "__", rel) + ".txt")
            out_file.write_text(text, encoding="utf-8")
            entry.update(extracted=str(out_file.relative_to(inbox)), chars=len(text), type=guess_type(p.name, text))
            status = "new" if not prev else "updated"
        else:
            entry.update(type=guess_type(p.name, ""), chars=0)
        entry["incorporated"] = False  # Claude sets this to true after updating the master resume
        manifest[rel] = entry
        rows.append((rel, entry["type"], status, entry.get("chars", 0)))

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if not rows:
        print(f"Inbox is empty: drop resumes, project docs, certificates or transcripts into {inbox}/")
        return
    print(f"{'file':48} {'type guess':15} {'status':14} chars")
    for rel, t, st, n in rows:
        print(f"{rel[:48]:48} {t:15} {st:14} {n}")
    todo = [r for r in rows if r[2] in ("new", "updated", "needs-vision")]
    pending = [k for k, v in manifest.items() if not v.get("incorporated")]
    print(f"\n{len(todo)} file(s) to review now · {len(pending)} not yet incorporated into the master resume")
    print(f"Extracted text: {out_dir}/   ·   needs-vision = open the original file and read it visually")


if __name__ == "__main__":
    main()
