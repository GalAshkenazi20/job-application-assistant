#!/usr/bin/env python3
"""
ATS keyword match + quick fit estimate: compares job descriptions with one or more resumes.

Single job (detailed report):
  python3 tools/ats_match.py resume_data/target_jobs/<job>.md
  python3 tools/ats_match.py <job>.md -r resume_data/master_resume.md -r <tailored>.md --out <report>.md
  python3 tools/ats_match.py <job>.md --json
Several jobs (ranked shortlist table, used in a search round):
  python3 tools/ats_match.py resume_data/target_jobs/*.md --candidate-years 0 --out shortlist.md

How the numbers work
  ATS coverage  - every known technology/skill found in the job description gets a priority:
                    required  (weight 3)  Requirements / Must / "דרישות" section, or a line with must/required/"חובה"
                    context   (weight 2)  role description / responsibilities / anywhere else
                    preferred (weight 1)  Advantage / Nice-to-have / "יתרון" section or line
                  coverage % = weight of JD keywords found in the resume / total weight.
                  A resume skill can satisfy related keywords (MySQL -> SQL, GitHub -> Git), marked "implied".
                  HTML comments in the resume (notes, VERIFY) are ignored.
  OR-lists      - "one of Java, Python, Go or C#" counts as satisfied when the resume has any of them
                  (marked "alternative").
  Eligibility   - "at least 1.5 years left in the degree", "2+ years remaining": compared with
                  --years-left (time the candidate has left in the degree). Failing it caps quick fit at 30.
                  Experience lines with an alternative ("3 years, or a strong graduate with side projects")
                  are reported as flexible and do not lower seniority fit.
  Quick fit     - keyword fit x seniority factor, where
                    keyword fit      = 0.6 x required-keyword coverage + 0.4 x ATS coverage
                    seniority factor = 0.4 + 0.6 x seniority fit   (seniority fit 0-100% -> factor 0.4-1.0)
                  Seniority fit compares the JD's years-of-EXPERIENCE requirement (and senior titles) with
                  --candidate-years, so a perfect keyword match for a senior role still ranks low.
                  It is a fast filter for ranking many jobs; the "overall match" in match_analysis.md adds
                  human judgment on must-haves and project relevance.
"""
import argparse
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from skills_dictionary import SKILLS  # noqa: E402

WEIGHTS = OrderedDict([("required", 3), ("context", 2), ("preferred", 1)])

PREF_HDR = re.compile(r"advantage|nice[- ]to[- ]have|preferred|bonus|\bplus\b|great if|יתרון|יתרונות", re.I)
REQ_HDR = re.compile(r"requirement|qualification|must[- ]have|what you(?:'ll)? (?:need|bring)|looking for|who you are|you have|you bring|\bskills\b|דרישות|כישורים|מה אנחנו מחפשים|חובה", re.I)
CTX_HDR = re.compile(r"responsibilit|what you(?:'ll)? do|about the|the role|role description|job description|day[- ]to[- ]day|benefits|offer|תיאור|תחומי אחריות|על התפקיד|מה תעשה|about us|who we are", re.I)
PREF_INLINE = re.compile(r"advantage|nice[- ]to[- ]have|preferred|\ba plus\b|\bis a plus\b|bonus|יתרון", re.I)
REQ_INLINE = re.compile(r"\bmust\b|\brequired\b|\bmandatory\b|\bessential\b|חובה", re.I)
NUM_RE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?%?")
BULLET = re.compile(r"^\s*(?:[-*•●▪◦·]|\d+[.)])\s+")

YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:(?:-|–|to)\s*(\d+)\s*)?\+?\s*years?|(\d+)\s*\+?\s*שנ(?:ים|ות|ה|ת)", re.I)
EXPERIENCE_WORDS = re.compile(r"experienc|hands[- ]on|background|ניסיון", re.I)
FLEX_EXPERIENCE = re.compile(r"\bor\b[^.;]*\b(graduate|student|equivalent|side projects|degree|bootcamp)|או בוגר|או סטודנט", re.I)
YEARS_LEFT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+?\s*(?:more\s+)?years?\s*(?:left|remaining|until graduation|to graduat|of studies left)"
    r"|(\d+)\s*\+?\s*semesters?\s*(?:left|remaining)"
    r"|(\d+(?:\.\d+)?)\s*\+?\s*שנ\S*\s*(?:לפחות\s*)?(?:לסיום|ללימודים|נוספות)", re.I)
OR_HINT = re.compile(r"\bone of\b|\bone or more\b|\bat least one\b|\bsuch as\b|\be\.g\.|\bany of\b|\bor\b|/|אחת מ|או ", re.I)
SENIOR_TITLE = re.compile(r"\b(senior|sr\.?|lead|principal|staff|architect|head of|manager)\b|בכיר|ראש צוות", re.I)
JUNIOR_RE = re.compile(r"\b(student|junior|jr\.|entry[- ]level|graduate|intern(?:ship)?|no experience)\b|סטודנט|ג'וניור|משרת סטודנט|בוגר", re.I)

ACRONYM_STOP = {
    "CV", "HR", "US", "USA", "IL", "OR", "AND", "THE", "WE", "IT", "ID", "PM", "AM", "EU", "UK", "FAQ",
    "CEO", "CTO", "COO", "CFO", "VP", "RD", "TLV", "LTD", "INC", "NOT", "ALL", "OUR", "YOU", "ARE", "FOR",
    "WITH", "JOB", "ROLE", "NEW", "TBD", "ASAP", "E.G", "I.E", "ETC", "N/A", "B.SC", "M.SC", "PHD", "BA", "MA",
}


def default_resume():
    for base in (Path.cwd(), HERE.parent):
        p = base / "resume_data" / "master_resume.md"
        if p.exists():
            return p
    return Path.cwd() / "resume_data" / "master_resume.md"


def read_text(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def clean_resume(text):
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)       # notes / VERIFY comments
    text = re.sub(r"\]\([^)]*\)", "]", text)                   # markdown link targets (URLs)
    text = re.sub(r"<[^>]+>", " ", text)                       # inline HTML tags
    return text


def split_jd(text):
    """Returns (title, description). The job template keeps the description under '## Job Description'."""
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    title_m = re.search(r"^#\s+(.+)$", text, flags=re.M)
    title = title_m.group(1).strip() if title_m else next((l.strip() for l in text.splitlines() if l.strip()), "")
    m = re.search(r"^#+\s*Job Description.*$", text, flags=re.M | re.I)
    body = text[m.end():] if m else text
    return title, body


def compile_skills():
    return [(name, cat, [re.compile(p, re.I) for p in pats], implies) for name, cat, pats, implies in SKILLS]


def header_kind(line):
    s = line.strip().strip("#*_ ").strip()
    if not s or BULLET.match(line) or len(s) > 70:
        return None
    looks_header = line.lstrip().startswith("#") or s.endswith(":") or len(s.split()) <= 6
    if not looks_header:
        return None
    if PREF_HDR.search(s):
        return "preferred"
    if REQ_HDR.search(s):
        return "required"
    if CTX_HDR.search(s):
        return "context"
    return "context" if s.endswith(":") else None


def extract_jd(jd_text, skills):
    """Returns (found, groups). groups = list of sets of skills listed as alternatives on one line."""
    found = OrderedDict()
    groups = []
    section = "context"
    for raw in jd_text.splitlines():
        if not raw.strip():
            continue
        kind = header_kind(raw)
        if kind:
            section = kind
        tier = section
        if PREF_INLINE.search(raw):
            tier = "preferred"
        elif REQ_INLINE.search(raw):
            tier = "required"
        in_line = {}
        for name, cat, pats, _ in skills:
            if any(p.search(raw) for p in pats):
                in_line.setdefault(cat, set()).add(name)
                cur = found.get(name)
                if cur is None or WEIGHTS[tier] > WEIGHTS[cur["tier"]]:
                    found[name] = {"category": cat, "tier": tier, "example": raw.strip()[:110]}
        if OR_HINT.search(raw):
            for cat, names in in_line.items():
                if len(names) >= 2 and cat in ("language", "backend", "frontend", "database", "mobile", "devops", "ai", "testing"):
                    groups.append(set(names))
    return found, groups


def resume_skills(text, skills):
    direct = {name for name, _, pats, _ in skills if any(p.search(text) for p in pats)}
    implies = {name: imp for name, _, _, imp in skills}
    have = set(direct)
    changed = True
    while changed:
        changed = False
        for s in list(have):
            for i in implies.get(s, []):
                if i not in have:
                    have.add(i)
                    changed = True
    return direct, have


def experience_requirements(jd_text):
    """Years mentioned next to 'experience' count as requirements; other year mentions are listed separately."""
    exp, other = [], []
    for line in jd_text.splitlines():
        if YEARS_LEFT_RE.search(line):
            continue  # time-left-in-degree lines are eligibility, see degree_time_left()
        for m in YEARS_RE.finditer(line):
            nums = [float(g) for g in m.groups() if g]
            entry = {"years": min(nums) if nums else 0, "text": line.strip()[:110],
                     "flexible": bool(FLEX_EXPERIENCE.search(line))}
            (exp if EXPERIENCE_WORDS.search(line) else other).append(entry)
    return exp, other


def degree_time_left(jd_text):
    """Largest 'years left in the degree' requirement in the JD (0 if none)."""
    req, lines = 0.0, []
    for line in jd_text.splitlines():
        for m in YEARS_LEFT_RE.finditer(line):
            y = float(m.group(1)) if m.group(1) else (int(m.group(2)) / 2 if m.group(2) else float(m.group(3)))
            req = max(req, y)
            lines.append(line.strip()[:110])
    return req, lines


def seniority_fit(title, jd_text, candidate_years):
    exp, _ = experience_requirements(jd_text)
    req = max((e["years"] for e in exp if not e["flexible"]), default=0)
    score = 100 if req <= candidate_years else max(0, 100 - 35 * (req - candidate_years))
    senior_title = bool(SENIOR_TITLE.search(title))
    if senior_title and candidate_years < 4:
        score = min(score, 15)
    return round(score), req, senior_title


def unrecognized_terms(jd_text, skills, resume_texts):
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.\-/]*[A-Za-z0-9+#]|[A-Za-z]{2,}", jd_text)
    counts = Counter()
    joined = " ".join(resume_texts).lower()
    for t in tokens:
        t = t.strip(".-/")
        if len(t) < 2:
            continue
        has_inner_upper = any(c.isupper() for c in t[1:])
        techy = has_inner_upper or any(c.isdigit() for c in t) or any(c in "+#." for c in t)
        if not techy:
            continue
        if t.upper() in ACRONYM_STOP or (t.isupper() and t.isalpha() and len(t) > 5):
            continue
        if any(p.search(t) for _, _, pats, _ in skills for p in pats):
            continue
        if t.lower() in joined:
            continue
        counts[t] += 1
    return counts.most_common(20)


def analyze(jd_path, resume_paths, candidate_years=0, skills=None, years_left=None):
    skills = skills or compile_skills()
    title, jd_text = split_jd(read_text(jd_path))
    jd, groups = extract_jd(jd_text, skills)
    left_req, left_lines = degree_time_left(jd_text)
    eligible = None if years_left is None or not left_req else years_left >= left_req
    total_w = sum(WEIGHTS[v["tier"]] for v in jd.values()) or 1
    sen_score, req_years, senior_title = seniority_fit(title, jd_text, candidate_years)

    resumes = []
    for rp in resume_paths:
        text = clean_resume(read_text(rp))
        direct, have = resume_skills(text, skills)
        status = {n: ("direct" if n in direct else "implied" if n in have else "missing") for n in jd}
        for g in groups:  # "one of X, Y or Z": any member satisfies the others
            if any(status.get(n) in ("direct", "implied") for n in g):
                for n in g:
                    if status.get(n) == "missing":
                        status[n] = "alternative"
        got_w = sum(WEIGHTS[jd[n]["tier"]] for n, s in status.items() if s != "missing")
        tiers = {}
        for t in WEIGHTS:
            names = [n for n in jd if jd[n]["tier"] == t]
            tiers[t] = {"found": sum(1 for n in names if status[n] != "missing"), "total": len(names)}
        coverage = round(100.0 * got_w / total_w, 1) if jd else 0.0
        req = tiers["required"]
        req_cov = 100.0 * req["found"] / req["total"] if req["total"] else coverage
        quick = round((0.6 * req_cov + 0.4 * coverage) * (0.4 + 0.6 * sen_score / 100))
        if eligible is False:
            quick = min(quick, 30)
        resumes.append({"file": str(rp), "label": Path(rp).stem, "text": text, "coverage": coverage,
                        "required_coverage": round(req_cov, 1), "quick_fit": quick, "tiers": tiers, "status": status})

    # Fact check: anything in a tailored resume that the baseline (master) does not contain
    if len(resumes) > 1:
        base_have = resume_skills(resumes[0]["text"], skills)[1]
        base_nums = set(NUM_RE.findall(resumes[0]["text"]))
        for r in resumes[1:]:
            r["not_in_master"] = {
                "skills": sorted(resume_skills(r["text"], skills)[0] - base_have),
                "numbers": sorted(set(NUM_RE.findall(r["text"])) - base_nums),
            }

    exp, other_years = experience_requirements(jd_text)
    junior = sorted({m.group(0).lower() for m in JUNIOR_RE.finditer(jd_text + " " + title)})
    return {"job": str(jd_path), "title": title, "jd_keywords": jd, "resumes": resumes,
            "seniority": {"score": sen_score, "required_years": req_years, "senior_title": senior_title,
                          "candidate_years": candidate_years, "junior_signals": junior},
            "experience_requirements": exp, "other_year_mentions": other_years,
            "degree_time_left": {"required_years": left_req, "lines": left_lines, "candidate_years_left": years_left,
                                 "eligible": eligible},
            "unrecognized_terms": unrecognized_terms(jd_text, skills, [r["text"] for r in resumes])}


def mark(s):
    return {"direct": "✅", "implied": "✅ (implied)", "alternative": "✅ (alternative)", "missing": "❌"}[s]


def to_markdown(res):
    jd, rs, sen = res["jd_keywords"], res["resumes"], res["seniority"]
    out = [f"# ATS Keyword Match – {res['title'] or Path(res['job']).stem}", ""]
    out.append(f"Job file: `{res['job']}`  ")
    out.append("Resumes: " + ", ".join(f"`{r['label']}`" for r in rs))
    out += ["", "## Scores", ""]
    out.append("| Resume | ATS coverage | Required | Context | Preferred | Quick fit |")
    out.append("|---|---|---|---|---|---|")
    for r in rs:
        t = r["tiers"]
        out.append(f"| {r['label']} | **{r['coverage']}%** | "
                   + " | ".join(f"{t[k]['found']}/{t[k]['total']}" for k in WEIGHTS) + f" | **{r['quick_fit']}%** |")
    out += ["", f"Weights: required = 3, context = 2, preferred = 1. Seniority fit = {sen['score']}% "
            f"(JD asks for {sen['required_years']:g} years of experience, candidate has {sen['candidate_years']:g}"
            + ("; senior title" if sen["senior_title"] else "") + ").", ""]

    out += ["## Keywords found in the job description", ""]
    out.append("| Keyword | Category | JD priority | " + " | ".join(r["label"] for r in rs) + " |")
    out.append("|---|---|---|" + "---|" * len(rs))
    order = sorted(jd, key=lambda n: (-WEIGHTS[jd[n]["tier"]], jd[n]["category"], n.lower()))
    for n in order:
        out.append(f"| {n} | {jd[n]['category']} | {jd[n]['tier']} | "
                   + " | ".join(mark(r["status"][n]) for r in rs) + " |")
    if not jd:
        out.append("| (no known keywords found – check that the job text was pasted) | | | " + " | " * len(rs))

    last = rs[-1]
    missing = [n for n in order if last["status"][n] == "missing"]
    out += ["", f"## Missing from `{last['label']}`", ""]
    out += [f"- **{n}** ({jd[n]['tier']}) – JD: \"{jd[n]['example']}\"" for n in missing] or \
           ["- None – every recognized JD keyword is covered."]

    if len(rs) > 1:
        base = rs[0]
        for r in rs[1:]:
            lost = [n for n in order if base["status"][n] != "missing" and r["status"][n] == "missing"]
            out += ["", f"## Lost in tailoring (`{base['label']}` has it, `{r['label']}` does not)", ""]
            out += [f"- **{n}** ({jd[n]['tier']})" for n in lost] or ["- None ✅"]
            extra = r.get("not_in_master", {})
            out += ["", f"## Fact check – in `{r['label']}` but not in `{base['label']}`", ""]
            if extra.get("skills") or extra.get("numbers"):
                if extra.get("skills"):
                    out.append("- ⚠️ Skills: " + ", ".join(extra["skills"]) + " – add to the master only if true, otherwise remove")
                if extra.get("numbers"):
                    out.append("- ⚠️ Numbers: " + ", ".join(extra["numbers"]) + " – every number must come from the master")
            else:
                out.append("- None ✅ (no new skills or numbers)")

    out += ["", "## Experience / seniority signals", ""]
    out += [f"- Experience: {e['years']:g}+ years{' (flexible – has an alternative)' if e['flexible'] else ''} – \"{e['text']}\""
            for e in res["experience_requirements"]] or ["- No years-of-experience requirement found."]
    dl = res["degree_time_left"]
    if dl["required_years"]:
        verdict = {None: "compare with the candidate's time left", True: "✅ candidate qualifies",
                   False: f"⚠️ candidate has {dl['candidate_years_left']:g} – likely filtered out"}[dl["eligible"]]
        out.append(f"- Time left in the degree: at least {dl['required_years']:g} years – {verdict}")
    out += [f"- Other year mention (not experience): \"{e['text']}\"" for e in res["other_year_mentions"]]
    if sen["junior_signals"]:
        out.append("- Junior/student signals: " + ", ".join(sen["junior_signals"]))
    if sen["senior_title"]:
        out.append("- ⚠️ Senior-level title")

    out += ["", "## Unrecognized technical terms (not in the dictionary, not in the resume – review manually)", ""]
    out.append(", ".join(f"`{t}`×{c}" if c > 1 else f"`{t}`" for t, c in res["unrecognized_terms"])
               if res["unrecognized_terms"] else "- None")
    out.append("")
    return "\n".join(out)


def batch_markdown(results):
    rows = sorted(results, key=lambda r: -r["resumes"][0]["quick_fit"])
    out = ["# Job shortlist – ranked by quick fit", "",
           f"Resume: `{rows[0]['resumes'][0]['label']}` · candidate experience: "
           f"{rows[0]['seniority']['candidate_years']:g} years", "",
           "| # | Job | Quick fit | ATS coverage | Required keywords | Seniority | Eligibility | Top missing (required) | File |",
           "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        rv, jd = r["resumes"][0], r["jd_keywords"]
        req = rv["tiers"]["required"]
        miss = [n for n in jd if jd[n]["tier"] == "required" and rv["status"][n] == "missing"][:3]
        dl = r["degree_time_left"]
        elig = "–" if not dl["required_years"] else (f"⚠️ needs {dl['required_years']:g}y left" if dl["eligible"] is False
                                                    else f"{dl['required_years']:g}y left ✅" if dl["eligible"] else f"needs {dl['required_years']:g}y left")
        out.append(f"| {i} | {r['title']} | **{rv['quick_fit']}%** | {rv['coverage']}% | {req['found']}/{req['total']} | "
                   f"{r['seniority']['score']}% | {elig} | {', '.join(miss) or '–'} | `{Path(r['job']).name}` |")
    out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("jobs", nargs="+", help="job description file(s) (.md / .txt); several = ranked batch table")
    ap.add_argument("-r", "--resume", action="append",
                    help="resume .md (repeatable; first = baseline). Default: resume_data/master_resume.md")
    ap.add_argument("--candidate-years", type=float, default=0,
                    help="candidate's years of professional experience in the field (default 0)")
    ap.add_argument("--years-left", type=float,
                    help="time the candidate has left in the degree, in years (0 = graduated); checks 'X years left' requirements")
    ap.add_argument("--out", help="write the markdown report to this file")
    ap.add_argument("--json", action="store_true", help="print JSON instead of markdown")
    a = ap.parse_args()
    resumes = a.resume or [default_resume()]
    skills = compile_skills()
    jobs = [j for j in a.jobs if not Path(j).name.startswith("_TEMPLATE")]
    results = [analyze(j, resumes, a.candidate_years, skills, a.years_left) for j in jobs]
    for res in results:
        for r in res["resumes"]:
            r.pop("text", None) if a.json else None
    if a.json:
        print(json.dumps(results if len(results) > 1 else results[0], ensure_ascii=False, indent=2))
        return
    md = batch_markdown(results) if len(results) > 1 else to_markdown(results[0])
    if a.out:
        Path(a.out).write_text(md, encoding="utf-8")
        print(f"Report written to {a.out}")
        for res in results:
            for r in res["resumes"]:
                print(f"{Path(res['job']).name} | {r['label']}: ATS {r['coverage']}% · quick fit {r['quick_fit']}%")
    else:
        print(md)


if __name__ == "__main__":
    main()
