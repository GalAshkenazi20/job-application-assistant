#!/usr/bin/env python3
"""
Find job posts in exported WhatsApp group chats (the many Israeli "משרות הייטק" / student-job groups).

WhatsApp is never automated: the candidate exports the chats themselves and drops the files in
inbox/whatsapp/.  Phone: open the group -> ⋮ (Android) or the group name (iPhone) -> Export chat ->
Without media -> save the .txt or .zip and copy it to inbox/whatsapp/ on the computer.

Usage (from the workspace folder):
  python3 tools/whatsapp_jobs.py                                  # inbox/whatsapp, last 30 days
  python3 tools/whatsapp_jobs.py inbox/whatsapp --days 14 --to-target-jobs resume_data/target_jobs

Output:
  a report (stdout or --out) with every job post found: date, group, title line, emails, links, text
  --to-target-jobs DIR : also saves each post as a job file (same format as templates/job_template.md),
                         so tools/ats_match.py can rank them with the other jobs of the round.
Privacy: only messages that look like job posts are kept; sender names and phone numbers are dropped.
Cross-posted duplicates (the same ad in several groups) are merged.
"""
import argparse
import hashlib
import re
import sys
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

sys.dont_write_bytecode = True

# Android: "26/10/2026, 14:05 - Name: text"   iOS: "[26/10/2026, 14:05:33] Name: text"   (also . or - in dates, AM/PM)
LINE_RE = re.compile(
    r"^‎?\[?(?P<d>\d{1,2})[./-](?P<m>\d{1,2})[./-](?P<y>\d{2,4}),?\s+(?P<t>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AaPp]\.?[Mm]\.?)?)\]?"
    r"\s*(?:-\s*)?(?P<rest>.*)$")
JOB_WORDS = re.compile(
    r"דרוש|דרושה|דרושים|דרוש/ה|משרה|משרת|מגייס|מגייסת|גיוס|מחפשים|מחפשת|הצטרפ|קו\"ח|קורות חיים|"
    r"\bhiring\b|\bjob\b|\bposition\b|\bopening\b|\bwe(?:'re| are) looking\b|\bjoin our\b|\bapply\b|\bCV\b|\bresume\b", re.I)
TECH_WORDS = re.compile(
    r"develop|מפתח|פיתוח|software|תוכנה|backend|back-end|frontend|front-end|full.?stack|fullstack|\bQA\b|automation|"
    r"אוטומציה|\bdata\b|python|java|android|\bios\b|devops|engineer|מהנדס|הנדסת|algorithm|אלגוריתם|embedded|"
    r"\bC\+\+|\bAI\b|\bML\b|machine learning|cyber|סייבר|הייטק|hi-?tech|מדעי המחשב|computer science|\bIT\b", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL_RE = re.compile(r"https?://[^\s<>\"']+|(?:www\.)[^\s<>\"']+")
PHONE_RE = re.compile(r"(?:\+972|0)(?:[\s-]?\d){8,9}")
SYSTEM_RE = re.compile(r"Messages and calls are end-to-end encrypted|ההודעות והשיחות|<Media omitted>|<המדיה הושמטה>|"
                       r"This message was deleted|ההודעה נמחקה|joined using this group|הצטרף/ה באמצעות", re.I)


def read_chat(path):
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".txt")]
            return "\n".join(z.read(n).decode("utf-8", errors="replace") for n in names)
    return path.read_text(encoding="utf-8", errors="replace")


def parse_messages(text):
    msgs, cur = [], None
    for line in text.splitlines():
        m = LINE_RE.match(line)
        if m:
            if cur:
                msgs.append(cur)
            y = int(m["y"]) + (2000 if len(m["y"]) == 2 else 0)
            try:
                when = date(y, int(m["m"]), int(m["d"]))
            except ValueError:  # month/day order differs (US export) – try swapped
                try:
                    when = date(y, int(m["d"]), int(m["m"]))
                except ValueError:
                    when = None
            rest = m["rest"]
            body = rest.split(": ", 1)[1] if ": " in rest else rest  # drop the sender name
            cur = {"date": when, "text": body}
        elif cur is not None:
            cur["text"] += "\n" + line
    if cur:
        msgs.append(cur)
    return msgs


def is_job_post(text):
    if SYSTEM_RE.search(text) and len(text) < 120:
        return False
    return len(text) >= 60 and bool(JOB_WORDS.search(text)) and bool(TECH_WORDS.search(text))


def fingerprint(text):
    norm = re.sub(r"\W+", "", text.lower())[:400]
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def title_of(text):
    for line in text.splitlines():
        line = re.sub(r"[*_~]", "", line).strip(" -•:‎‏")
        if len(line) >= 6 and not EMAIL_RE.fullmatch(line) and not URL_RE.match(line):
            return line[:90]
    return "Job post"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", default="inbox/whatsapp")
    ap.add_argument("--days", type=int, default=30, help="only posts from the last N days (default 30)")
    ap.add_argument("--out", help="write the report to this markdown file")
    ap.add_argument("--to-target-jobs", metavar="DIR", help="also save each post as a job file in DIR")
    a = ap.parse_args()

    folder = Path(a.folder)
    files = sorted(p for p in folder.glob("*") if p.suffix.lower() in (".txt", ".zip")) if folder.is_dir() else []
    if not files:
        print(f"No exported chats in {folder}/ – export each WhatsApp group (Export chat -> Without media) "
              f"and copy the .txt/.zip here.")
        return
    since = date.today() - timedelta(days=a.days)
    posts, seen = [], {}
    total = 0
    for f in files:
        group = re.sub(r"^(WhatsApp Chat with|צ'אט WhatsApp עם|WhatsApp Chat -)\s*", "", f.stem).strip() or f.stem
        for msg in parse_messages(read_chat(f)):
            total += 1
            if msg["date"] and msg["date"] < since:
                continue
            text = msg["text"].strip()
            if not is_job_post(text):
                continue
            fp = fingerprint(text)
            if fp in seen:
                seen[fp]["groups"].add(group)
                continue
            clean = PHONE_RE.sub("[phone removed]", text)
            post = {"date": msg["date"], "groups": {group}, "title": title_of(clean), "text": clean,
                    "emails": sorted(set(EMAIL_RE.findall(text))), "links": sorted(set(URL_RE.findall(text)))}
            seen[fp] = post
            posts.append(post)

    posts.sort(key=lambda p: p["date"] or date.min, reverse=True)
    out = [f"# WhatsApp job posts – last {a.days} days", "",
           f"{len(files)} chat file(s), {total} messages scanned, {len(posts)} job post(s) found.", ""]
    for i, p in enumerate(posts, 1):
        out += [f"## {i}. {p['title']}", "",
                f"- **Date:** {p['date'] or 'unknown'} · **Group(s):** {', '.join(sorted(p['groups']))}",
                f"- **Apply by email:** {', '.join(p['emails']) or '–'}",
                f"- **Links:** {', '.join(p['links']) or '–'}", "", "```", p["text"], "```", ""]
    report = "\n".join(out)
    if a.out:
        Path(a.out).write_text(report, encoding="utf-8")
        print(f"Report: {a.out}  ({len(posts)} job posts)")
    else:
        print(report)

    if a.to_target_jobs and posts:
        d = Path(a.to_target_jobs)
        d.mkdir(parents=True, exist_ok=True)
        for p in posts:
            slug = re.sub(r"[^\w]+", "-", p["title"], flags=re.UNICODE).strip("-")[:50] or "job"
            name = f"{p['date'] or date.today()}_WhatsApp_{slug}.md"
            path = d / name
            if path.exists():
                continue
            how = ("email " + ", ".join(p["emails"])) if p["emails"] else ("link " + p["links"][0] if p["links"] else "see post")
            path.write_text(
                f"# WhatsApp – {p['title']}\n\n- **Company:** (see post)\n- **Role:** {p['title']}\n"
                f"- **Link:** {p['links'][0] if p['links'] else '–'}\n- **How to apply:** {how}\n"
                f"- **Source:** WhatsApp group(s): {', '.join(sorted(p['groups']))}\n"
                f"- **Date saved:** {date.today()} (posted {p['date'] or 'unknown'})\n\n## Job Description\n\n{p['text']}\n",
                encoding="utf-8")
        print(f"Saved {len(posts)} job file(s) to {d}/ (existing files kept)")


if __name__ == "__main__":
    main()
