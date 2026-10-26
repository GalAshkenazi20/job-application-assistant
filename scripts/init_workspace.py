#!/usr/bin/env python3
"""
Create or upgrade a personal job-search workspace.

Usage:
  python3 <skill>/scripts/init_workspace.py ~/Desktop/Job_Assistant
  python3 <skill>/scripts/init_workspace.py <workspace> --update-tools    # force-refresh tools/ and templates/

Layout it creates (existing personal files are NEVER overwritten):
  <workspace>/
    README.md                         short guide (created once)
    inbox/                            drop zone: old resumes, project docs, certificates, transcripts
    inbox/whatsapp/                   exported WhatsApp job-group chats (tools/whatsapp_jobs.py)
    resume_data/
      master_resume.md                single source of truth (from templates/master_resume_template.md)
      preferences.md                  what jobs to look for (from templates/preferences_template.md)
      applications_tracker.csv        one row per job (tools/tracker.py)
      target_jobs/_TEMPLATE_job.md    saved job descriptions
      applications_output/            one folder per application
    templates/                        copied from the skill (updated when the skill version is newer)
    tools/                            copied scripts + resume.css + VERSION + SKILL.md + references/ (same rule)
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOOL_FILES = ["ats_match.py", "skills_dictionary.py", "build_pdf.py", "ingest.py", "tracker.py",
              "whatsapp_jobs.py", "init_workspace.py", "self_test.py"]

WORKSPACE_README = """# Job search workspace

Personal data lives here and stays on this computer. Ask Claude (with the job-application-assistant skill):

- "Here are my files" → drop old resumes, project write-ups, certificates and transcripts into `inbox/`
  and Claude builds / updates `resume_data/master_resume.md`.
- Paste a job description or link → tailored resume (PDF), cover letter, match analysis and interview prep
  in `resume_data/applications_output/<date>_<company>_<role>/`.
- "Find jobs for me" → Claude asks your preferences (saved in `resume_data/preferences.md`), searches,
  ranks jobs by match %, and applies to the ones you approve.
- Open `dashboard.html` to see every application, its match score, files and next actions.
"""

INBOX_README = """# Inbox – drop files here

Drag anything that describes your experience into this folder: old resumes (PDF/Word), project
write-ups or READMEs, certificates, transcripts, recommendation letters, screenshots of course
completions. Then tell Claude "I added files to the inbox".

Claude extracts the text with tools/ingest.py, reads images directly, and updates
resume_data/master_resume.md. Your original files are never changed or deleted.
"""


def version_of(path):
    try:
        return tuple(int(x) for x in path.read_text().strip().split("."))
    except Exception:
        return (0,)


def copy(src, dst, report, label):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    report.append(f"{label:9} {dst}")


def create_if_missing(dst, content, report):
    if dst.exists():
        report.append(f"kept      {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content, encoding="utf-8")
    report.append(f"created   {dst}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", nargs="?", default=".")
    ap.add_argument("--update-tools", action="store_true", help="refresh tools/ and templates/ even if not newer")
    a = ap.parse_args()

    ws = Path(a.workspace).expanduser()
    report = []
    for d in ("inbox", "inbox/whatsapp", "resume_data/target_jobs", "resume_data/applications_output", "templates", "tools"):
        (ws / d).mkdir(parents=True, exist_ok=True)

    skill_v = version_of(ROOT / "VERSION") if (ROOT / "VERSION").exists() else version_of(HERE / "VERSION")
    ws_v = version_of(ws / "tools" / "VERSION")
    refresh = a.update_tools or skill_v > ws_v or not (ws / "tools" / "ats_match.py").exists()
    same_place = (ws / "tools").resolve() == HERE

    if refresh and not same_place:
        for f in TOOL_FILES:
            if (HERE / f).exists():
                copy(HERE / f, ws / "tools" / f, report, "tools")
        css = HERE / "resume.css" if (HERE / "resume.css").exists() else ROOT / "assets" / "resume.css"
        copy(css, ws / "tools" / "resume.css", report, "tools")
        (ws / "tools" / "VERSION").write_text(".".join(map(str, skill_v)) + "\n")
        tpl_dir = ROOT / "templates"
        for t in sorted(tpl_dir.glob("*.md")):
            copy(t, ws / "templates" / t.name, report, "templates")
        # Workflow docs + SKILL.md travel with the tools, so the skill works even when it was
        # installed as a single SKILL.md (e.g. saved to a Claude account without its folders).
        ref_dir = ROOT / "references" if (ROOT / "references").is_dir() else HERE / "references"
        for r in sorted(ref_dir.glob("*.md")):
            copy(r, ws / "tools" / "references" / r.name, report, "tools")
        skill_md = ROOT / "SKILL.md" if (ROOT / "SKILL.md").exists() else HERE / "SKILL.md"
        if skill_md.exists():
            copy(skill_md, ws / "tools" / "SKILL.md", report, "tools")
    else:
        report.append(f"up to date tools/ + templates/ (version {'.'.join(map(str, ws_v))})")

    tpl = ws / "templates"
    def tpl_text(name, fallback=""):
        p = tpl / name if (tpl / name).exists() else ROOT / "templates" / name
        return p.read_text(encoding="utf-8") if p.exists() else fallback

    create_if_missing(ws / "README.md", WORKSPACE_README, report)
    create_if_missing(ws / "inbox" / "README.md", INBOX_README, report)
    create_if_missing(ws / "resume_data" / "master_resume.md", tpl_text("master_resume_template.md"), report)
    create_if_missing(ws / "resume_data" / "preferences.md", tpl_text("preferences_template.md"), report)
    create_if_missing(ws / "resume_data" / "target_jobs" / "_TEMPLATE_job.md", tpl_text("job_template.md"), report)
    create_if_missing(ws / "resume_data" / "applications_tracker.csv",
                      "id,company,role,status,quick_fit,match_score,ats_master,ats_tailored,location,source,channel,"
                      "link,job_file,folder,date_found,date_applied,follow_up,notes\n", report)

    print(f"Workspace: {ws.resolve()}")
    for line in report:
        print("  " + line)


if __name__ == "__main__":
    main()
