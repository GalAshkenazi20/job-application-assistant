# Workflow: build or update the master resume from the candidate's files

Goal: turn whatever the candidate drops in (old resumes, project write-ups, certificates, transcripts,
recommendation letters, GitHub links, things they say in chat) into one accurate, complete
`resume_data/master_resume.md`. Everything later depends on this file, so accuracy beats speed here.

## 1. Collect

- **Inbox folder:** files dropped into `<workspace>/inbox/`.
- **Chat uploads:** files attached to the conversation – copy them into `inbox/` first so they are
  processed and kept like everything else.
- **Links:** GitHub profile or repos, LinkedIn, portfolio. Read public pages (READMEs give project
  details, stacks and numbers). Note each link as a source.

## 2. Extract

```bash
python3 tools/ingest.py            # new/changed files only; originals are never touched
```

Read every `inbox/_extracted/*.txt` listed as new/updated. For files marked **needs-vision** (photos,
scanned certificates, image-only PDFs) open the original file and read it directly.

## 3. Classify and merge

For each source, decide what it adds:

| Source type | Goes to |
|---|---|
| old resume | every section – compare with the master line by line |
| project write-up / README | Projects: what it is, stack, the candidate's part, numbers |
| certificate / course | Certifications (name, issuer, year) and Technical Skills if a real skill |
| transcript | Education: degree, years, GPA only if strong, 4–6 relevant courses |
| recommendation letter | Not copied into the resume. Note the recommender as a possible reference |
| job ad | Not profile data – save it in `target_jobs/` and run the tailoring workflow |

Rules while merging:

- **Keep the candidate's facts, improve the wording.** Rewrite bullets with the formula in
  `resume_writing.md`, but never change a number, date, title or scope.
- **Conflicts:** when two sources disagree (dates, tech used, a metric), keep the most recent, put
  the other in a `<!-- VERIFY: ... -->` comment, and ask the candidate. Do not silently pick one.
- **Sources:** add `<!-- source: inbox/<file> -->` after facts that came from a file, so the
  candidate (and later runs) can trace them.
- **No inflation:** a course is not "experience", a tutorial is not a "project", a team project
  says what *this* candidate did.
- **Skills need evidence.** A skill listed with no project, job or course behind it gets a
  `<!-- NOTE: no project shows X yet -->` so interview prep can flag it.
- Keep the master's structure (`# name`, headline, contact, `##` sections, `###` entries with
  `<span class="right">` for dates/links). Longer than one page is fine for the master.

## 4. Confirm and record

1. Show the candidate a short summary in chat: what was added, what changed, open questions (VERIFY).
2. After they confirm, mark the files as incorporated:
   `python3 tools/ingest.py --done <file> <file> ...`
3. Optional preview: `python3 tools/build_pdf.py resume_data/master_resume.md` (the master has no page limit).
4. Update the `Last updated` date in the master's top comment.

## Missing information worth asking for (only what changes outcomes)

Dates for jobs and the degree, GitHub links for projects, measurable results (users, accuracy,
latency, number of endpoints/tests), GPA if strong, availability (hours/week, start date),
languages, military service (relevant in Israel), work authorization if applying abroad.
