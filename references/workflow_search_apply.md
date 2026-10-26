# Workflow: find jobs → rank by match → one approval → apply → follow up

This is the "do it for me" round. The candidate approves once per round; Claude does the rest,
with a final confirmation before any website form is submitted. Quality beats volume: a few
well-matched, tailored applications get more interviews than a hundred generic ones, and
recruiters notice (and remember) spray-and-pray.

## 0. Preferences

Read `resume_data/preferences.md`. If it is missing, still has `{{...}}` in the "What to look for"
part, or is older than ~2 months, ask before searching – with the environment's question tool if it
has one (multiple-choice, max ~4 questions per round), otherwise in plain text:

1. Target roles (offer 3–4 options derived from the master resume, e.g. Backend Student / Junior
   Android / ML Student) – multi-select.
2. Job type and hours (student position 20–24h · junior full-time · internship).
3. Locations / remote / hybrid.
4. Minimum match to shortlist (65% recommended) and max applications per round (8 recommended).

Ask about companies to target/avoid and deal-breakers only if the answers above leave it open.
Save the answers to `preferences.md` (template: `templates/preferences_template.md`).

## 1. Search

Combine preferences with the sources in `job_sources.md`. Collect roughly 2–3× the round limit.

- Run several focused searches (role × location × source) rather than one broad one.
- Prefer postings from the last ~3 weeks; skip ones marked closed/expired.
- Open each promising posting and copy the **full** description – snippets are not enough to score.
- Save each as `resume_data/target_jobs/YYYY-MM-DD_Company_Role.md` with Link, Source and
  **How to apply** (email address / company form URL / LinkedIn Easy Apply / referral only).
- Skip duplicates: `python3 tools/tracker.py list` – the same link or company + role is already tracked.
- Jobs the user pasted or linked join the same round.
- **Job alerts in email:** if an email tool is connected, search it for job-alert emails from the last
  ~3 weeks (LinkedIn `jobalerts-noreply@linkedin.com` / `jobs-noreply@linkedin.com`, AllJobs, Drushim,
  Glassdoor, Indeed) and for jobs the candidate saved. They are the candidate's own data, already filtered
  to their profile – often the best LinkedIn source, since LinkedIn pages cannot be read automatically.
- **WhatsApp groups:** `python3 tools/whatsapp_jobs.py inbox/whatsapp --days 21 --to-target-jobs resume_data/target_jobs`
  on chats the candidate exported (never automate WhatsApp itself). Posts with an email address are the
  easiest to apply to.
- Career sites that render with JavaScript (Comeet, Apple, Amazon, Workday) need a browser tool to read;
  if none is available, look for the same posting on a job board mirror or ask the candidate to paste it.
- Max 2 roles per company per round (recruiters see all of them).

## 2. Rank

```bash
python3 tools/ats_match.py resume_data/target_jobs/<this round's files> --candidate-years N --years-left Y \
        --out resume_data/applications_output/_rounds/YYYY-MM-DD_shortlist.md
```

`--years-left` (time left in the degree, from preferences) makes the table flag student roles that ask for
"at least 1.5 / 2 years left" – a very common filter in Israeli student positions.

The batch table ranks by **quick fit**. For each job at or above the threshold, skim the must-haves
yourself – the tool cannot read "at least 2 years left in the degree", "security clearance",
"Hebrew + Arabic", "must live in Haifa". Drop jobs that fail a hard requirement and say why.
Track them: `tracker.py add ... --quick-fit Q --status shortlisted` (or `--status skipped` with a note).

## 3. The one-click approval

Show the shortlist in chat as a compact table: #, company, role, quick fit %, one-line "why you fit",
main gap, how to apply, link. Then ask ONE question (with the question tool when available):

- **Apply to all N shortlisted (recommended)**
- **Only the top 3**
- **Let me choose** (the candidate replies with numbers)
- **Not now** (keep the shortlist; nothing is sent)

The answer is the approval for this round. Mark chosen jobs `approved`, the rest stay `shortlisted`.

## 4. Prepare

Run `workflow_tailor.md` for each approved job (tailored resume PDF, cover letter, analysis, prep,
outreach). Every quality gate must pass; a job that fails a gate is not submitted until fixed.
Status → `prepared`.

## 5. Submit – by channel

| Channel | How | Approval |
|---|---|---|
| **Email address in the ad** | Connected email tool (e.g. a Gmail connector): subject + body from `outreach.md` §2, attach the resume PDF and cover letter PDF. If the tool can only create drafts, or cannot attach files, create the drafts and tell the candidate exactly which drafts to open and send. | Covered by the round approval |
| **Company application form** (Comeet, Greenhouse, Lever, SmartRecruiters, Workday, a company site) | Browser tool: open the form, fill the fields from the master resume and preferences, upload the tailored PDF, paste the cover letter where there is a field, take a screenshot. **Stop before Submit.** After all forms are filled, ask once: "Submit these N forms?" – then submit each and confirm the success page. | Round approval + one final confirmation |
| **LinkedIn Easy Apply, or any site whose terms forbid automated applying** | Do not automate. Give the candidate the link, the tailored PDF and the answers to paste. | The candidate clicks |
| **Referral-only / "send to a friend"** | Prepare `outreach.md` §1; the candidate sends it to their contact. | The candidate sends |

While filling forms:
- Answer screening questions only from facts in the master resume and preferences. Anything else
  (salary expectation, relocation, "how did you hear about us", legal/visa, diversity questions) –
  ask the candidate, or leave optional questions empty.
- Never create accounts, type passwords, solve CAPTCHAs or pay. Hand those steps to the candidate
  and continue after they are done.
- If a form needs a document that does not exist (transcript, recommendation letter), stop and tell
  the candidate; a recommendation letter is drafted with the recommender, never invented.
- If no email or browser tool is available, prepare everything and give the candidate a ready
  checklist (link → file → text to paste) – that is still most of the work done.

After each submission: `tracker.py update <id> --status applied --channel <email|form|easy-apply|referral>`
(this sets the follow-up date to +7 days), then regenerate the dashboard.

## 6. Report and follow up

- Round summary: applied (with match %), waiting for the candidate (Easy Apply / referrals),
  skipped and why, open questions. Point to `dashboard.html`.
- Offer a follow-up check in 7 days if the environment can schedule tasks. On that check:
  `tracker.py due` → draft follow-ups from `outreach.md` §4 for jobs with no answer; ask the candidate
  to update statuses for replies, interviews and rejections.
- When an interview is scheduled: status `interview`, refresh `interview_prep.md` with what is known
  about the interviewers and the stage.

## Honesty and safety rules for this workflow

- Apply only to jobs the candidate approved in this round – never "while I'm at it".
- Never claim anything the master resume does not support, in a form, an email or a letter.
- Respect each site's terms; when in doubt, hand the click to the candidate.
- Personal data (phone, email, documents) goes only to the employer the candidate approved.
