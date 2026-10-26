#!/usr/bin/env python3
"""
Application tracker + accessible dashboard.  Data: resume_data/applications_tracker.csv (one row per job).

Usage (from the workspace folder):
  python3 tools/tracker.py add --company Wix --role "Backend Developer Student" --link URL --quick-fit 78 \
                               --job-file resume_data/target_jobs/2026-10-27_Wix_Backend.md
  python3 tools/tracker.py update 3 --status applied --channel email --folder 2026-10-27_Wix_Backend
  python3 tools/tracker.py list [--status shortlisted]
  python3 tools/tracker.py due                      # follow-ups that are due today or earlier
  python3 tools/tracker.py dashboard [--lang he]    # writes dashboard.html in the workspace root

Statuses (in order): found, shortlisted, approved, prepared, applied, hr_screen, interview, final, offer,
                     rejected, withdrawn, skipped
"add" never duplicates: the same link, or the same company + role, updates the existing row instead.
Setting status=applied fills date_applied (today) and follow_up (+7 days) if they are empty.
"""
import argparse
import csv
import html
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.dont_write_bytecode = True
FIELDS = ["id", "company", "role", "status", "quick_fit", "match_score", "ats_master", "ats_tailored",
          "location", "source", "channel", "link", "job_file", "folder", "date_found", "date_applied",
          "follow_up", "notes"]
STATUSES = ["found", "shortlisted", "approved", "prepared", "applied", "hr_screen", "interview", "final",
            "offer", "rejected", "withdrawn", "skipped"]
CSV_PATH = Path("resume_data/applications_tracker.csv")
OUTPUT_DIR = Path("resume_data/applications_output")


def load():
    if not CSV_PATH.exists():
        return []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return [{k: (r.get(k) or "") for k in FIELDS} for r in csv.DictReader(f)]


def save(rows):
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def apply_fields(row, values):
    for k, v in values.items():
        if v is not None and k in FIELDS and k != "id":
            row[k] = str(v)
    if row["status"] == "applied":
        if not row["date_applied"]:
            row["date_applied"] = date.today().isoformat()
        if not row["follow_up"]:
            row["follow_up"] = (date.fromisoformat(row["date_applied"]) + timedelta(days=7)).isoformat()


def find_existing(rows, link, company, role):
    for r in rows:
        if link and r["link"] and r["link"].strip().rstrip("/") == link.strip().rstrip("/"):
            return r
        if company and role and r["company"].strip().lower() == company.strip().lower() \
                and r["role"].strip().lower() == role.strip().lower():
            return r
    return None


def fmt_table(rows):
    cols = ["id", "status", "quick_fit", "match_score", "company", "role", "date_applied", "follow_up"]
    out = [" | ".join(cols)]
    for r in rows:
        out.append(" | ".join(r[c] or "-" for c in cols))
    return "\n".join(out)


# ----------------------------------------------------------------- dashboard
LABELS = {
    "en": {"title": "Job search dashboard", "updated": "Updated", "skip": "Skip to applications",
           "total": "Jobs tracked", "applied": "Applied", "interviews": "Interviews", "offers": "Offers",
           "due": "Follow-ups due", "next": "Next actions", "none": "Nothing waiting – nice.",
           "apps": "Applications", "filter": "Status", "all": "All", "search": "Search company or role",
           "company": "Company", "role": "Role", "status": "Status", "fit": "Quick fit", "match": "Match",
           "ats": "ATS (master / tailored)", "applied_on": "Applied", "follow": "Follow-up", "files": "Files",
           "job": "Job post", "empty": "No applications yet. Ask Claude to find jobs or paste a job description.",
           "act_due": "Send a follow-up", "act_approved": "Prepare the application package",
           "act_prepared": "Submit the application", "act_short": "Approve or skip",
           "inbox": "Inbox files not yet in the master resume", "sort": "Sort by",
           "caption": "All tracked jobs. Use the column buttons to sort."},
    "he": {"title": "לוח חיפוש עבודה", "updated": "עודכן", "skip": "דלג לטבלת המועמדויות",
           "total": "משרות במעקב", "applied": "הוגשו", "interviews": "ראיונות", "offers": "הצעות",
           "due": "פולואפים להיום", "next": "הצעדים הבאים", "none": "אין משימות פתוחות.",
           "apps": "מועמדויות", "filter": "סטטוס", "all": "הכל", "search": "חיפוש חברה או תפקיד",
           "company": "חברה", "role": "תפקיד", "status": "סטטוס", "fit": "התאמה מהירה", "match": "ציון התאמה",
           "ats": "ATS (מקורי / מותאם)", "applied_on": "הוגש", "follow": "פולואפ", "files": "קבצים",
           "job": "המשרה", "empty": "עוד אין מועמדויות. בקש מ-Claude למצוא משרות או הדבק תיאור משרה.",
           "act_due": "לשלוח פולואפ", "act_approved": "להכין חבילת מועמדות", "act_prepared": "להגיש",
           "act_short": "לאשר או לדלג", "inbox": "קבצים בתיבת הקליטה שעוד לא נכנסו ל-master",
           "sort": "מיון לפי", "caption": "כל המשרות במעקב. אפשר למיין בלחיצה על כותרות העמודות."},
}
STATUS_LABELS = {
    "en": {s: s.replace("_", " ") for s in STATUSES},
    "he": {"found": "נמצאה", "shortlisted": "ברשימה קצרה", "approved": "אושרה להגשה", "prepared": "מוכנה",
           "applied": "הוגשה", "hr_screen": "שיחת HR", "interview": "ראיון", "final": "ראיון סופי",
           "offer": "הצעה", "rejected": "נדחתה", "withdrawn": "בוטלה", "skipped": "דולגה"},
}
STATUS_ICON = {"found": "○", "shortlisted": "☆", "approved": "✓", "prepared": "▣", "applied": "➤",
               "hr_screen": "☎", "interview": "◆", "final": "◆◆", "offer": "★", "rejected": "✕",
               "withdrawn": "–", "skipped": "–"}


def folder_files(folder):
    d = OUTPUT_DIR / folder if folder else None
    if not d or not d.is_dir():
        return []
    keep = [p for p in sorted(d.iterdir()) if p.suffix.lower() in (".pdf", ".md") and not p.name.startswith("ats_")]
    pdf_stems = {p.stem for p in keep if p.suffix.lower() == ".pdf"}
    return [str(p).replace("\\", "/") for p in keep if p.suffix.lower() == ".pdf" or p.stem not in pdf_stems]


def inbox_pending():
    m = Path("inbox/_extracted/manifest.json")
    if not m.exists():
        return []
    data = json.loads(m.read_text(encoding="utf-8"))
    return [k for k, v in data.items() if not v.get("incorporated")]


def dashboard(rows, lang, out):
    L, S = LABELS[lang], STATUS_LABELS[lang]
    today = date.today().isoformat()
    n_applied = sum(1 for r in rows if r["status"] in STATUSES[4:9])
    n_int = sum(1 for r in rows if r["status"] in ("interview", "final", "offer"))
    n_offer = sum(1 for r in rows if r["status"] == "offer")
    due = [r for r in rows if r["status"] == "applied" and r["follow_up"] and r["follow_up"] <= today]
    actions = [(L["act_due"], r) for r in due]
    actions += [(L["act_prepared"], r) for r in rows if r["status"] == "prepared"]
    actions += [(L["act_approved"], r) for r in rows if r["status"] == "approved"]
    actions += [(L["act_short"], r) for r in rows if r["status"] == "shortlisted"]
    pending = inbox_pending()

    data = []
    for r in rows:
        data.append({**{k: r[k] for k in FIELDS}, "status_label": S.get(r["status"], r["status"]),
                     "icon": STATUS_ICON.get(r["status"], "•"), "files": folder_files(r["folder"]),
                     "due": bool(r in due)})
    e = html.escape
    act_html = "".join(f'<li><strong>{e(a)}</strong> – {e(r["company"])}, {e(r["role"])}</li>' for a, r in actions) \
        or f"<li>{e(L['none'])}</li>"
    if pending:
        act_html += f'<li><strong>{e(L["inbox"])}</strong>: {e(", ".join(pending[:8]))}</li>'
    opts = "".join(f'<option value="{s}">{e(S[s])}</option>' for s in STATUSES)
    dir_attr = 'dir="rtl"' if lang == "he" else 'dir="ltr"'
    cols = [("company", L["company"]), ("role", L["role"]), ("status", L["status"]), ("quick_fit", L["fit"]),
            ("match_score", L["match"]), ("ats", L["ats"]), ("date_applied", L["applied_on"]),
            ("follow_up", L["follow"]), ("files", L["files"])]
    sortable = {"company", "role", "status", "quick_fit", "match_score", "date_applied", "follow_up"}
    th = "".join(
        (f'<th scope="col" aria-sort="none" data-key="{k}"><button type="button" aria-label="{e(L["sort"])} {e(lbl)}">'
         f'{e(lbl)}<span aria-hidden="true" class="arrow"></span></button></th>') if k in sortable
        else f'<th scope="col">{e(lbl)}</th>' for k, lbl in cols)

    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    labels_json = json.dumps({"job": L["job"]}, ensure_ascii=False)
    order_json = json.dumps(STATUSES)
    page = f"""<!doctype html>
<html lang="{lang}" {dir_attr}>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(L['title'])}</title>
<style>
:root {{ --bg:#f7f8fa; --card:#fff; --text:#16191d; --muted:#4a5260; --line:#d5d9e0; --accent:#1f3a5f;
  --ok:#1e6b34; --warn:#8a5a00; --bad:#a3231a; --focus:#0b5fff; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#111418; --card:#1a1f26; --text:#eef1f5; --muted:#b4bccb;
  --line:#2f3743; --accent:#9cc0f0; --ok:#7fd49a; --warn:#f2c46b; --bad:#ff9b92; --focus:#8fb4ff; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:16px/1.5 "Segoe UI", Arial, sans-serif; }}
main {{ max-width:1200px; margin:0 auto; padding:24px 16px 48px; }}
a {{ color:var(--accent); }}
.skip {{ position:absolute; inset-inline-start:8px; top:-80px; background:var(--card); padding:8px 12px; border:2px solid var(--focus); }}
.skip:focus {{ top:8px; }}
:focus-visible {{ outline:3px solid var(--focus); outline-offset:2px; }}
h1 {{ font-size:1.6rem; margin:0 0 4px; }} h2 {{ font-size:1.2rem; margin:28px 0 10px; }}
.muted {{ color:var(--muted); font-size:.9rem; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-top:16px; padding:0; list-style:none; }}
.stats li {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 14px; }}
.stats b {{ display:block; font-size:1.7rem; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 16px; }}
.controls {{ display:flex; flex-wrap:wrap; gap:12px; align-items:end; margin-bottom:10px; }}
label {{ display:flex; flex-direction:column; font-size:.9rem; color:var(--muted); gap:4px; }}
select, input {{ font:inherit; padding:6px 8px; border:1px solid var(--line); border-radius:6px; background:var(--card); color:var(--text); min-width:200px; }}
.tablewrap {{ overflow-x:auto; background:var(--card); border:1px solid var(--line); border-radius:10px; }}
table {{ border-collapse:collapse; width:100%; min-width:900px; }}
caption {{ text-align:start; padding:10px 12px; color:var(--muted); font-size:.9rem; }}
th, td {{ padding:9px 12px; border-top:1px solid var(--line); text-align:start; vertical-align:top; }}
th button {{ font:inherit; font-weight:600; background:none; border:0; color:var(--text); cursor:pointer; padding:0; }}
.badge {{ display:inline-block; padding:1px 8px; border-radius:999px; border:1px solid var(--line); white-space:nowrap; }}
.s-offer, .s-interview, .s-final {{ color:var(--ok); border-color:var(--ok); }}
.s-rejected {{ color:var(--bad); border-color:var(--bad); }}
.s-applied, .s-hr_screen {{ color:var(--accent); border-color:var(--accent); }}
.due {{ color:var(--warn); font-weight:600; }}
.num {{ font-variant-numeric:tabular-nums; white-space:nowrap; }}
ul.files {{ margin:0; padding-inline-start:18px; }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition:none !important; }} }}
</style></head>
<body>
<a class="skip" href="#apps">{e(L['skip'])}</a>
<main>
<header><h1>{e(L['title'])}</h1><p class="muted">{e(L['updated'])}: {today}</p></header>
<ul class="stats" aria-label="{e(L['title'])}">
<li><b class="num">{len(rows)}</b>{e(L['total'])}</li><li><b class="num">{n_applied}</b>{e(L['applied'])}</li>
<li><b class="num">{n_int}</b>{e(L['interviews'])}</li><li><b class="num">{n_offer}</b>{e(L['offers'])}</li>
<li><b class="num">{len(due)}</b>{e(L['due'])}</li></ul>
<section aria-labelledby="next-h"><h2 id="next-h">{e(L['next'])}</h2><div class="card"><ul>{act_html}</ul></div></section>
<section aria-labelledby="apps-h"><h2 id="apps-h">{e(L['apps'])}</h2>
<div class="controls">
<label>{e(L['filter'])}<select id="f-status"><option value="">{e(L['all'])}</option>{opts}</select></label>
<label>{e(L['search'])}<input id="f-q" type="search"></label></div>
<div class="tablewrap"><table id="apps"><caption>{e(L['caption'])}</caption>
<thead><tr>{th}</tr></thead><tbody></tbody></table></div>
<p id="empty" class="muted" hidden>{e(L['empty'])}</p>
<p class="muted" aria-live="polite" id="count"></p></section>
</main>
<script type="application/json" id="data">{data_json}</script>
<script>
const rows = JSON.parse(document.getElementById('data').textContent);
const L = {labels_json};
const order = {order_json};
let sortKey = 'quick_fit', dir = -1;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const num = v => v === '' ? -1 : parseFloat(v);
function cmp(a, b) {{
  if (sortKey === 'status') return (order.indexOf(a.status) - order.indexOf(b.status)) * dir;
  if (['quick_fit','match_score'].includes(sortKey)) return (num(a[sortKey]) - num(b[sortKey])) * dir;
  return String(a[sortKey]).localeCompare(String(b[sortKey])) * dir;
}}
function render() {{
  const st = document.getElementById('f-status').value, q = document.getElementById('f-q').value.trim().toLowerCase();
  const list = rows.filter(r => (!st || r.status === st) && (!q || (r.company + ' ' + r.role).toLowerCase().includes(q))).sort(cmp);
  document.querySelector('#apps tbody').innerHTML = list.map(r => `<tr>
    <td>${{esc(r.company)}}</td>
    <td>${{r.link ? `<a href="${{esc(r.link)}}" target="_blank" rel="noopener">${{esc(r.role)}}</a>` : esc(r.role)}}</td>
    <td><span class="badge s-${{esc(r.status)}}"><span aria-hidden="true">${{esc(r.icon)}}</span> ${{esc(r.status_label)}}</span></td>
    <td class="num">${{r.quick_fit ? esc(r.quick_fit) + '%' : '–'}}</td>
    <td class="num">${{r.match_score ? esc(r.match_score) + '/100' : '–'}}</td>
    <td class="num"><bdi dir="ltr">${{r.ats_master ? esc(r.ats_master) + '%' : '–'}}${{r.ats_tailored ? ' / ' + esc(r.ats_tailored) + '%' : ''}}</bdi></td>
    <td class="num"><bdi dir="ltr">${{esc(r.date_applied) || '–'}}</bdi></td>
    <td class="num ${{r.due ? 'due' : ''}}"><bdi dir="ltr">${{esc(r.follow_up) || '–'}}</bdi>${{r.due ? ' ⚑' : ''}}</td>
    <td>${{r.files.length ? '<ul class="files">' + r.files.map(f => `<li><a href="${{esc(f)}}">${{esc(f.split('/').pop())}}</a></li>`).join('') + '</ul>' : '–'}}</td>
  </tr>`).join('');
  document.getElementById('empty').hidden = rows.length > 0;
  document.getElementById('count').textContent = list.length + ' / ' + rows.length;
  document.querySelectorAll('th[data-key]').forEach(th => {{
    const on = th.dataset.key === sortKey;
    th.setAttribute('aria-sort', on ? (dir > 0 ? 'ascending' : 'descending') : 'none');
    th.querySelector('.arrow').textContent = on ? (dir > 0 ? ' ▲' : ' ▼') : '';
  }});
}}
document.querySelectorAll('th[data-key] button').forEach(b => b.addEventListener('click', () => {{
  const k = b.parentElement.dataset.key; dir = (k === sortKey) ? -dir : (['quick_fit','match_score','date_applied','follow_up'].includes(k) ? -1 : 1); sortKey = k; render();
}}));
document.getElementById('f-status').addEventListener('change', render);
document.getElementById('f-q').addEventListener('input', render);
render();
</script>
</body></html>
"""
    Path(out).write_text(page, encoding="utf-8")
    print(f"Dashboard: {out}  ({len(rows)} jobs, {len(actions)} next actions)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("add", "update"):
        p = sub.add_parser(name)
        if name == "update":
            p.add_argument("id")
        for f in FIELDS[1:]:
            p.add_argument("--" + f.replace("_", "-"), dest=f)
    pl = sub.add_parser("list")
    pl.add_argument("--status")
    sub.add_parser("due")
    pd = sub.add_parser("dashboard")
    pd.add_argument("--lang", choices=["en", "he"], default="en")
    pd.add_argument("--out", default="dashboard.html")
    a = ap.parse_args()
    rows = load()

    if a.cmd in ("add", "update"):
        values = {f: getattr(a, f) for f in FIELDS[1:]}
        if values.get("status") and values["status"] not in STATUSES:
            sys.exit(f"Unknown status '{values['status']}'. Use one of: {', '.join(STATUSES)}")
        if a.cmd == "add":
            if not (a.company and a.role):
                sys.exit("add needs --company and --role")
            row = find_existing(rows, a.link, a.company, a.role)
            if row:
                apply_fields(row, {k: v for k, v in values.items() if k not in ("company", "role")})
                print(f"exists – updated #{row['id']}")
            else:
                row = {k: "" for k in FIELDS}
                row["id"] = str(max((int(r["id"]) for r in rows if r["id"].isdigit()), default=0) + 1)
                row["status"], row["date_found"] = "found", date.today().isoformat()
                apply_fields(row, values)
                rows.append(row)
                print(f"added #{row['id']}")
        else:
            row = next((r for r in rows if r["id"] == str(a.id)), None)
            if not row:
                sys.exit(f"No application with id {a.id}")
            apply_fields(row, values)
            print(f"updated #{row['id']}")
        save(rows)
    elif a.cmd == "list":
        print(fmt_table([r for r in rows if not a.status or r["status"] == a.status]))
    elif a.cmd == "due":
        today = date.today().isoformat()
        print(fmt_table([r for r in rows if r["status"] == "applied" and r["follow_up"] and r["follow_up"] <= today]))
    elif a.cmd == "dashboard":
        dashboard(rows, a.lang, a.out)


if __name__ == "__main__":
    main()
