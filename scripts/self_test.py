#!/usr/bin/env python3
"""
Self-test for the job-application-assistant tools.   Run:  python3 tools/self_test.py
(or python3 scripts/self_test.py inside the skill). Uses only a temporary folder - never touches your files.
Covers: keyword detection edge cases, priority tiers, scoring math, quick fit / seniority, batch ranking,
inbox ingestion, tracker + dashboard, PDF builder safety checks and workspace creation.
"""
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ats_match as A  # noqa: E402
import build_pdf as B  # noqa: E402

SK = A.compile_skills()
results = []
PY = sys.executable
try:
    import markdown  # noqa: F401
    HAVE_MD = True
except ImportError:
    HAVE_MD = False
try:
    import weasyprint  # noqa: F401
    HAVE_PDF = HAVE_MD
except ImportError:
    HAVE_PDF = False


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def run(args, cwd):
    return subprocess.run([PY, *map(str, args)], cwd=cwd, capture_output=True, text=True,
                          env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin:/usr/local/bin"})


def found(text):
    return A.resume_skills(text, SK)[0]


def implied(text):
    return A.resume_skills(text, SK)[1]


# ---------------------------------------------------------------- keyword detection
f = found("Strong knowledge of C/C++ and Python")
check("C/C++ -> C and C++", {"C", "C++"} <= f, f)
f = found("Experience with C# and .NET")
check("C# is not C", "C#" in f and "C" not in f, f)
check("Objective-C is not C", "C" not in found("Objective-C developers"))
check("C-level is not C", "C" not in found("present to C-level executives"))
check("'Proficient in C.' -> C", "C" in found("Proficient in C."))
f = found("JavaScript, TypeScript")
check("JavaScript is not Java", "JavaScript" in f and "Java" not in f, f)
check("NoSQL is not SQL", "SQL" not in found("NoSQL databases"))
check("MySQL implies SQL (resume side)", "SQL" in implied("MySQL"))
check("GitHub implies Git", "Git" in implied("GitHub"))
check("'send your CV' is not computer vision", "Computer vision" not in found("Please send your CV"))
check("'the rest of the team' is not REST", "REST APIs" not in found("work with the rest of the team"))
check("REST detected", "REST APIs" in found("Design REST APIs"))
check("NodeJS and Node.js", "Node.js" in found("NodeJS") and "Node.js" in found("Node.js"))
check("'Node, Express' list", {"Node.js", "Express"} <= found("Node, Express, MongoDB"))
check("lowercase 'express' is not Express", "Express" not in found("express your ideas"))
check("Go in a list", "Go" in found("Python, Go, Java"))
check("'go to market' is not Go", "Go" not in found("help us go to market"))
check("Wav2Vec 2.0", "Wav2Vec" in found("Wav2Vec 2.0"))
check("Hebrew: אנגלית -> English", "English" in found("אנגלית ברמה גבוהה"))

# ---------------------------------------------------------------- tiers
jd = """About the role
You will build backend services in Node.js.

Requirements:
- Java - must
- Experience with REST APIs

Advantages:
- Docker
- Kubernetes is a plus
"""
t = A.extract_jd(jd, SK)[0]
check("required tier (Requirements section)", t.get("Java", {}).get("tier") == "required", t.get("Java"))
check("context tier (About the role)", t.get("Node.js", {}).get("tier") == "context", t.get("Node.js"))
check("preferred tier (Advantages section)", t.get("Docker", {}).get("tier") == "preferred", t.get("Docker"))
t = A.extract_jd("דרישות:\n- ניסיון ב-Python\n- ידע ב-Docker - יתרון\n", SK)[0]
check("Hebrew: דרישות -> required", t.get("Python", {}).get("tier") == "required", t.get("Python"))
check("Hebrew: יתרון line -> preferred", t.get("Docker", {}).get("tier") == "preferred", t.get("Docker"))

with tempfile.TemporaryDirectory() as d:
    d = Path(d)

    # ------------------------------------------------------------ scoring + quick fit
    (d / "job.md").write_text("# Co – Developer\n\nRequirements:\n- Java\n\nAdvantages:\n- Docker\n", encoding="utf-8")
    (d / "r.md").write_text("# Test Person\n\nJava developer.\n<!-- Docker -->\n", encoding="utf-8")
    res = A.analyze(d / "job.md", [d / "r.md"])
    rv = res["resumes"][0]
    check("score math: Java(3) of Java(3)+Docker(1) = 75%", rv["coverage"] == 75.0, rv["coverage"])
    check("HTML comment in resume is ignored", rv["status"]["Docker"] == "missing")
    check("quick fit = (.6*100 + .4*75) x 1.0 = 90", rv["quick_fit"] == 90, rv["quick_fit"])

    (d / "tailored.md").write_text("# Test Person\n\nJava and Kubernetes developer, 30% faster builds.\n", encoding="utf-8")
    res = A.analyze(d / "job.md", [d / "r.md", d / "tailored.md"])
    nim = res["resumes"][1].get("not_in_master", {})
    check("fact check flags a skill and a number missing from the master",
          "Kubernetes" in nim.get("skills", []) and "30%" in nim.get("numbers", []), nim)

    (d / "senior.md").write_text("# Co – Senior Backend Engineer\n\nRequirements:\n- 5+ years of experience with Java\n",
                                 encoding="utf-8")
    res = A.analyze(d / "senior.md", [d / "r.md"], candidate_years=0)
    check("5+ years experience vs 0 -> seniority 0", res["seniority"]["score"] == 0, res["seniority"])
    check("senior title detected", res["seniority"]["senior_title"])
    (d / "student.md").write_text("# Co – Developer Student\n\nRequirements:\n- Java\n"
                                  "- B.Sc. student with at least 1.5 years remaining\n", encoding="utf-8")
    res = A.analyze(d / "student.md", [d / "r.md"], years_left=0.5)
    check("'1.5 years remaining' is a degree-time requirement, not experience",
          res["seniority"]["required_years"] == 0 and res["degree_time_left"]["required_years"] == 1.5, res["degree_time_left"])
    check("candidate with 0.5 years left is flagged and quick fit capped at 30",
          res["degree_time_left"]["eligible"] is False and res["resumes"][0]["quick_fit"] <= 30, res["resumes"][0]["quick_fit"])
    res = A.analyze(d / "student.md", [d / "r.md"], years_left=2)
    check("candidate with 2 years left qualifies", res["degree_time_left"]["eligible"] is True)

    (d / "orlist.md").write_text("# Co – Graduate SDE\n\nBasic qualifications:\n- Experience with at least one language "
                                 "such as Java, Python, C++, C#, Go or TypeScript\n", encoding="utf-8")
    res = A.analyze(d / "orlist.md", [d / "r.md"])
    st = res["resumes"][0]["status"]
    check("'one of Java, Go, C#...' is satisfied by Java alone (alternatives)",
          st.get("Java") == "direct" and st.get("Go") == "alternative" and st.get("C#") == "alternative", st)

    (d / "flex.md").write_text("# Co – Software Engineer\n\nRequirements:\n- At least 3 years of hands-on backend experience, "
                               "or a strong graduate with serious side projects.\n- Java\n", encoding="utf-8")
    res = A.analyze(d / "flex.md", [d / "r.md"])
    check("'3 years, or a strong graduate' is flexible – seniority not penalized",
          res["seniority"]["score"] == 100 and res["experience_requirements"][0]["flexible"], res["seniority"])

    batch = A.batch_markdown([A.analyze(d / n, [d / "r.md"]) for n in ("senior.md", "student.md")])
    check("batch table ranks the better fit first",
          batch.index("Developer Student") < batch.index("Senior Backend Engineer"), batch)

    # ------------------------------------------------------------ workspace creation
    ws = d / "ws"
    p = run([HERE / "init_workspace.py", ws], d)
    layout_ok = all((ws / x).exists() for x in ("inbox", "resume_data/master_resume.md", "resume_data/preferences.md",
                                                 "resume_data/applications_tracker.csv", "tools/ats_match.py",
                                                 "tools/resume.css", "templates", "tools/references/workflow_tailor.md"))
    check("init_workspace creates the full layout", p.returncode == 0 and layout_ok, p.stdout + p.stderr)
    (ws / "resume_data/master_resume.md").write_text("# My Real Resume\n", encoding="utf-8")
    run([HERE / "init_workspace.py", ws, "--update-tools"], d)
    check("init_workspace never overwrites the master resume",
          (ws / "resume_data/master_resume.md").read_text(encoding="utf-8") == "# My Real Resume\n")

    # ------------------------------------------------------------ ingest
    inbox = ws / "inbox"
    (inbox / "old_cv.txt").write_text("Education: B.Sc. Computer Science. Experience: teaching. Skills: Java",
                                      encoding="utf-8")
    with zipfile.ZipFile(inbox / "aws_cert.docx", "w") as z:
        z.writestr("word/document.xml", '<w:document><w:body><w:p><w:r><w:t>Certificate of Completion</w:t></w:r></w:p>'
                   '<w:p><w:r><w:t>has successfully completed AWS Cloud Practitioner</w:t></w:r></w:p></w:body></w:document>')
    (inbox / "diploma.jpg").write_bytes(b"\xff\xd8\xff\xe0fakejpeg")
    p = run([ws / "tools/ingest.py", "inbox"], ws)
    man = json.loads((inbox / "_extracted/manifest.json").read_text(encoding="utf-8"))
    check("ingest: txt -> resume, docx -> certificate, jpg -> needs-vision",
          man.get("old_cv.txt", {}).get("type") == "resume" and man.get("aws_cert.docx", {}).get("type") == "certificate"
          and man.get("diploma.jpg", {}).get("status") == "needs-vision", json.dumps(man)[:400])
    check("ingest: README in inbox is skipped", "README.md" not in man)
    p = run([ws / "tools/ingest.py", "inbox"], ws)
    check("ingest: second run reports unchanged files", p.stdout.count("unchanged") == 3, p.stdout)
    run([ws / "tools/ingest.py", "inbox", "--done", "old_cv.txt"], ws)
    man = json.loads((inbox / "_extracted/manifest.json").read_text(encoding="utf-8"))
    check("ingest --done marks a file as incorporated", man["old_cv.txt"]["incorporated"] is True)

    # ------------------------------------------------------------ WhatsApp exports
    from datetime import date as _d, timedelta as _td
    today = _d.today()
    d1 = (today - _td(days=2)).strftime("%d/%m/%Y")
    d_old = (today - _td(days=90)).strftime("%d/%m/%Y")
    wa = ws / "inbox" / "whatsapp"
    wa.mkdir(parents=True, exist_ok=True)
    post = ("דרוש/ה מפתח/ת Backend ג'וניור לחברת סטארטאפ בתל אביב\nPython, Node.js, ידע ב-SQL\n"
            "קו\"ח ל- jobs@startup.example.com או 050-1234567")
    (wa / "WhatsApp Chat with Hitech Jobs.txt").write_text(
        f"{d1}, 10:05 - Dana Cohen: {post}\n{d1}, 11:00 - Avi: מישהו יודע מתי הכנס?\n"
        f"{d_old}, 09:00 - Old Poster: דרוש מפתח Java ותיק, משרה מלאה, קו\"ח ל old@example.com\n", encoding="utf-8")
    (wa / "students.txt").write_text(f"[{d1}, 12:30:00] Yossi: {post}\n", encoding="utf-8")
    p = run([ws / "tools/whatsapp_jobs.py", "inbox/whatsapp", "--days", "30", "--to-target-jobs", "resume_data/target_jobs"], ws)
    check("WhatsApp: 1 job found (Android + iOS formats, duplicate merged, chit-chat and old post ignored)",
          "1 job post(s) found" in p.stdout and "jobs@startup.example.com" in p.stdout and "Hitech Jobs" in p.stdout
          and "students" in p.stdout, p.stdout + p.stderr)
    check("WhatsApp: sender names and phone numbers are not kept",
          "Dana" not in p.stdout and "050-1234567" not in p.stdout and "[phone removed]" in p.stdout, p.stdout)
    saved = list((ws / "resume_data/target_jobs").glob("*_WhatsApp_*.md"))
    check("WhatsApp: post saved as a job file that ats_match can read",
          len(saved) == 1 and "## Job Description" in saved[0].read_text(encoding="utf-8"), saved)

    # ------------------------------------------------------------ tracker + dashboard
    tr = ws / "tools/tracker.py"
    run([tr, "add", "--company", "Acme", "--role", "Backend Student", "--link", "https://x.io/j/1", "--quick-fit", "80"], ws)
    p = run([tr, "add", "--company", "acme", "--role", "backend student", "--quick-fit", "82"], ws)
    check("tracker: same company+role updates instead of duplicating", "exists" in p.stdout, p.stdout)
    run([tr, "add", "--company", "<script>alert(1)</script>", "--role", "QA"], ws)
    p = run([tr, "update", "1", "--status", "applied"], ws)
    rows = (ws / "resume_data/applications_tracker.csv").read_text(encoding="utf-8").splitlines()
    check("tracker: 2 rows, applied row got date_applied + follow_up",
          len(rows) == 3 and rows[1].count("-") >= 4 and ",applied," in rows[1], rows)
    p = run([tr, "update", "1", "--status", "hired"], ws)
    check("tracker: unknown status rejected", p.returncode != 0)
    p = run([tr, "dashboard", "--lang", "he"], ws)
    page = (ws / "dashboard.html").read_text(encoding="utf-8")
    check("dashboard: Hebrew RTL page with the jobs", 'dir="rtl"' in page and "Acme" in page, p.stdout + p.stderr)
    check("dashboard: user text cannot inject a script tag", "<script>alert(1)</script>" not in page)
    check("dashboard: accessibility basics (caption, scope, aria-sort, labels, skip link)",
          all(x in page for x in ("<caption>", 'scope="col"', "aria-sort", "<label>", 'class="skip"')))

    # ------------------------------------------------------------ PDF builder
    if HAVE_MD:
        html = B.to_html("# T\n\n| a |\n|---|\n| ✅ 🟡 ❌ ⚠️ |\n", "t", "T", "doc")
        body = html[html.find("<body"):]
        check("build_pdf: emoji replaced by printable symbols",
              not any(e in body for e in "✅🟡❌️") and body.count("<span") == 4, body)
        check("build_pdf: Hebrew document is RTL", 'dir="rtl"' in B.to_html("# שלום\n\nזה מסמך בעברית", "t", "", "doc"))
    if HAVE_PDF:
        ok_md = d / "Test_Resume.md"
        ok_md.write_text("# Test Person\n\n**Developer**\n\nmail@example.com\n\n## Summary\n\n" + "Builds things. " * 30,
                         encoding="utf-8")
        p = run([HERE / "build_pdf.py", ok_md], d)
        check("build_pdf: clean resume passes", p.returncode == 0 and (d / "Test_Resume.pdf").exists(), p.stdout + p.stderr)
        bad_md = d / "Bad_Resume.md"
        bad_md.write_text("# Test Person\n\n**{{Headline}}**\n\n## Summary\n\n" + "Builds things. " * 30, encoding="utf-8")
        p = run([HERE / "build_pdf.py", bad_md], d)
        check("build_pdf: leftover {{placeholder}} is caught", p.returncode == 1 and "placeholder" in p.stdout, p.stdout)
        long_md = d / "Long_Resume.md"
        long_md.write_text("# Test Person\n\n" + "\n\n".join(f"## Section {i}\n\n" + "Text line. " * 60 for i in range(12)),
                           encoding="utf-8")
        p = run([HERE / "build_pdf.py", long_md], d)
        check("build_pdf: a 2-page resume is flagged", p.returncode == 1 and "pages" in p.stdout, p.stdout)
    else:
        print("(markdown/weasyprint not installed - PDF checks skipped: pip install --user markdown weasyprint)")

passed = sum(1 for _, ok, _ in results if ok)
for name, ok, detail in results:
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f"   -> {str(detail)[:600]}"))
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
