# Workflow: one job → a complete application package

Input: a job description (pasted text, a link, or a file in `target_jobs/`).
Output folder: `resume_data/applications_output/YYYY-MM-DD_Company_Role/` containing

| File | What |
|---|---|
| `<Name>_<Company>_<Role>.md` + `.pdf` | tailored resume, one page, ATS-friendly |
| `cover_letter.md` + `.pdf` | tailored cover letter |
| `match_analysis.md` | scores, requirements vs. evidence, gaps, recommendation |
| `interview_prep.md` | pitch, project deep-dives, expected questions with answer guidance |
| `outreach.md` | referral request, email body, LinkedIn note, follow-up (from the outreach template) |
| `ats_report_master.md`, `ats_report_tailored.md` | raw tool reports |
| `recommendation_draft_<name>.md` | only if the job asks for a recommendation letter (draft for the recommender) |

Use names without spaces (`Noa_Levi_Acme_Backend-Student.pdf`) – recruiters see the file name.

## Steps

1. **Save the job** with `templates/job_template.md` → `resume_data/target_jobs/YYYY-MM-DD_Company_Role.md`.
   Paste the description verbatim under `## Job Description`; fill Link and "How to apply".
   For a link, fetch the page and copy the full text. If the page cannot be read, ask the user to paste it.
2. **Create the application folder.** Add the job to the tracker if it is not there:
   `python3 tools/tracker.py add --company ... --role ... --link ... --job-file ...`
3. **Baseline:** `python3 tools/ats_match.py <job> --candidate-years N --out <app>/ats_report_master.md`
   (N = professional years from `preferences.md`, default 0).
4. **Map requirements to evidence.** For every requirement: ✅ / 🟡 / ❌ with the master line that proves it.
   Sort missing keywords into A (has it, wording missing), B (adjacent – frame honestly), C (real gap).
   If a C item looks like something the candidate may simply not have mentioned, ask – on "yes",
   add it to the master first.
5. **Write the tailored resume** (rules below).
6. **Re-run ATS on both:** `python3 tools/ats_match.py <job> -r resume_data/master_resume.md -r <app>/<resume>.md --candidate-years N --out <app>/ats_report_tailored.md`.
   Iterate until the quality gates pass.
7. **Build and look at the PDF:** `python3 tools/build_pdf.py <app>/<resume>.md` must print `CHECKS: ✅`.
   Then render the page to an image and look at it: nothing cut off, no heading stranded at the
   bottom, dates aligned, links present. Fix and rebuild if needed.
8. **match_analysis.md** from the template, in the candidate's language.
9. **cover_letter.md** from the template + `build_pdf.py`. One page.
10. **interview_prep.md** from the template, in the candidate's language.
11. **outreach.md** from the outreach template (skip sections that do not apply).
12. **Tracker:** `tracker.py update <id> --status prepared --folder <folder> --ats-master X --ats-tailored Y --quick-fit Q --match-score Z`,
    then `tracker.py dashboard --lang <he|en>`.
13. **Report** (short, candidate's language): ATS before → after, overall match, top 3 gaps and what to
    do about them, open questions, the file list.

## Tailored resume rules

- **One page** (two only for 5+ years of experience). Same markdown structure as the master so
  `resume.css` lays it out: `# name` → headline paragraph → contact paragraph → `##` sections →
  `###` entries with `<span class="right">` for dates/links.
- **Order:** Summary → Education → Technical Skills → Projects → Experience → (Certifications) →
  Military Service & Languages. Put Experience before Projects when the candidate has relevant industry
  experience. Standard section names only – ATS parsers look for them.
- **Headline:** the job's own title wording when truthful ("Backend Developer Student").
- **Summary:** 2–3 lines with the 4–6 most important job keywords, written for this role.
- **Skills:** the job's keywords first, in the job's exact spelling (Node.js vs NodeJS); drop
  categories that do not matter for this role.
- **Projects:** the 3–4 most relevant, most relevant first, 2–3 bullets each. Front-load the job's
  keywords and the outcome. Facts and numbers identical to the master.
- **Experience:** frame each role toward the job (e.g. teaching → communication, mentoring, the
  languages taught) without changing what was done.
- **No tables, columns, icons, photos or text boxes.** Plain text in a single column parses best.

## Quality gates (all must pass before reporting)

- [ ] Tailored ATS coverage ≥ master, and "Lost in tailoring" lists no **required** keyword.
- [ ] Every missing **required** keyword is explained in match_analysis.md (A/B/C).
- [ ] `build_pdf.py` prints `CHECKS: ✅` for the resume and the cover letter.
- [ ] The rendered page was looked at and is clean.
- [ ] Fact check: the report's "Fact check" section says None ✅ (no skill or number missing from the
      master), and every tailored bullet traces to a master line – also for soft claims the tool cannot
      see ("reviewed others' code", "led the team").
- [ ] Eligibility check: hard requirements the keyword tool cannot judge (time left in the degree,
      weekly hours, location, clearance, languages, work authorization) are compared with the facts.
      A requirement the candidate does not meet is a risk in match_analysis.md – the letter and
      forms never claim it ("more than 1.5 years left" when the degree ends next summer).
- [ ] Cover letter: 200–350 words, names the company and role, one concrete company detail, no clichés.
- [ ] Interview prep covers every required item, each tied to a real project or an honest gap answer.

## Overall match score (match_analysis.md)

| Component | Weight | How |
|---|---|---|
| Must-have requirements met | 40 | share of must-haves with ✅ (🟡 = half) × 40 |
| Keyword coverage (tailored) | 20 | tailored ATS coverage × 0.2 |
| Seniority fit | 20 | student/junior/no years = 20 · 1–2 years = 12 · 3+ years = 5 · senior = 0 |
| Project & domain relevance | 20 | judgment, explained in one line |

Bands: 80+ strong · 65–79 good · 50–64 stretch (apply with a referral or a clear angle) · <50 skip.
Say plainly that the score is an estimate of fit, not a prediction of the hiring decision.
