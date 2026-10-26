#!/usr/bin/env python3
"""
Markdown -> clean, ATS-friendly PDF (single column, real selectable text, clickable links).

Usage (from the workspace folder):
  python3 tools/build_pdf.py resume_data/applications_output/<folder>/<Name>_<Company>_<Role>.md
  python3 tools/build_pdf.py <cover_letter>.md                 (style picked from the file name)
  python3 tools/build_pdf.py <interview_prep>.md --style doc
  python3 tools/build_pdf.py resume_data/master_resume.md      (master: no page limit)

Options:
  --style resume|letter|doc   default from the file name: cover/letter/recommendation -> letter,
                              prep/analysis/report/outreach -> doc, anything else -> resume
  --max-pages N               fail the check if the PDF is longer (default 1 for resume/letter, 0 = no limit)
  --html                      also keep the intermediate .html

Self-checks after building (exit code 1 if any fails):
  * page count vs. --max-pages
  * text is extractable (pdftotext) and contains the candidate's name (the first "# " heading)
  * no leftover placeholders / notes: {{...}}, VERIFY, TODO, ADD:, XX
Markdown notes inside <!-- --> are removed. Hebrew documents are rendered right-to-left automatically.
Requires: pip install --user markdown weasyprint. Without weasyprint the .html is written instead
(open it in a browser -> Print -> Save as PDF).
"""
import argparse
import logging
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
logging.getLogger("fontTools").setLevel(logging.ERROR)
HERE = Path(__file__).resolve().parent
LEAKS = [r"\{\{", r"\}\}", r"\bVERIFY\b", r"\bTODO\b", r"\bADD:", r"\b20XX\b", r"\bXX+\b", r"<!--", r"\[\["]

# Colour emoji have no glyphs in the PDF fonts -> swap for plain symbols that always render
SYMBOLS = {"✅": '<span class="sym ok">✔</span>', "🟡": '<span class="sym mid">◐</span>',
           "❌": '<span class="sym no">✘</span>', "⚠": '<span class="sym warn">⚠</span>'}
SYMBOL_RE = re.compile("✅|🟡|❌|⚠️?")


def css_path():
    for p in (HERE / "resume.css", HERE.parent / "assets" / "resume.css"):
        if p.exists():
            return p
    sys.exit("resume.css not found next to build_pdf.py or in ../assets/")


def pick_style(name):
    n = name.lower()
    if any(k in n for k in ("cover", "letter", "recommendation")):
        return "letter"
    if any(k in n for k in ("prep", "analysis", "report", "ats_", "outreach", "shortlist")):
        return "doc"
    return "resume"


def is_hebrew(text):
    heb = len(re.findall(r"[֐-׿]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    return heb > 0 and heb / (heb + lat) > 0.3


def to_html(md_text, title, author, style):
    import markdown
    md_text = re.sub(r"<!--.*?-->", "", md_text, flags=re.S)
    md_text = SYMBOL_RE.sub(lambda m: SYMBOLS[m.group(0)[0]], md_text)
    body = markdown.markdown(md_text, extensions=["extra", "sane_lists"])
    css = css_path().read_text(encoding="utf-8")
    lang = 'lang="he" dir="rtl"' if is_hebrew(md_text) else 'lang="en"'
    return (f'<!doctype html><html {lang}><head><meta charset="utf-8"><title>{title}</title>'
            f'<meta name="author" content="{author}"><style>{css}</style></head>'
            f'<body class="{style}">{body}</body></html>')


def check_pdf(pdf_path, author):
    if not shutil.which("pdftotext"):
        return ["(pdftotext not installed - text-extraction check skipped)"]
    problems = []
    text = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"], capture_output=True, text=True).stdout
    if len(text.strip()) < 200:
        problems.append("PDF text is not extractable (an ATS would see an empty page)")
    if author and author.split()[0].lower() not in text.lower():
        problems.append(f"name '{author}' not found in the PDF text")
    for pat in LEAKS:
        for m in re.finditer(pat, text):
            line = text[max(0, text.rfind("\n", 0, m.start())):text.find("\n", m.end())].strip()
            problems.append(f"leftover placeholder/note: '{line[:90]}'")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("markdown_file")
    ap.add_argument("--out", help="output PDF path (default: same name, .pdf)")
    ap.add_argument("--style", choices=["resume", "letter", "doc"])
    ap.add_argument("--max-pages", type=int)
    ap.add_argument("--html", action="store_true", help="also keep the .html file")
    a = ap.parse_args()

    src = Path(a.markdown_file)
    md_text = src.read_text(encoding="utf-8")
    style = a.style or pick_style(src.name)
    h1 = re.search(r"^#\s+(.+)$", re.sub(r"<!--.*?-->", "", md_text, flags=re.S), flags=re.M)
    author = h1.group(1).strip() if h1 else ""
    title = src.stem.replace("_", " ")
    max_pages = a.max_pages if a.max_pages is not None else (0 if style == "doc" or "master" in src.stem else 1)

    html = to_html(md_text, title, author if style != "doc" else "", style)
    out = Path(a.out) if a.out else src.with_suffix(".pdf")
    html_path = src.with_suffix(".html")
    try:
        import weasyprint
    except ImportError:
        html_path.write_text(html, encoding="utf-8")
        print(f"weasyprint is not installed -> wrote {html_path}")
        print("Install: pip install --user markdown weasyprint   (or open the .html in a browser -> Print -> Save as PDF)")
        sys.exit(2)

    doc = weasyprint.HTML(string=html, base_url=str(src.parent.resolve())).render()
    pages = len(doc.pages)
    doc.write_pdf(str(out))
    if a.html:
        html_path.write_text(html, encoding="utf-8")

    print(f"PDF: {out}  ({pages} page{'s' if pages != 1 else ''}, style={style})")
    problems = check_pdf(out, author if style != "doc" else "")
    if max_pages and pages > max_pages:
        problems.insert(0, f"{pages} pages - longer than the {max_pages}-page target")
    if problems:
        print("CHECKS: ⚠️")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("CHECKS: ✅ page count OK, text extractable, no leftover placeholders")


if __name__ == "__main__":
    main()
