# Where to find jobs (Israel-focused, works elsewhere too)

Update this file when a source stops working or a better one appears.

## Sources

| Source | Good for | Apply channel |
|---|---|---|
| Company career pages on hiring platforms: **Comeet** (`comeet.com/jobs/...`), **Greenhouse** (`boards.greenhouse.io`, `job-boards.greenhouse.io`), **Lever** (`jobs.lever.co`), **Ashby** (`jobs.ashbyhq.com`), **SmartRecruiters**, **Workday** (`*.myworkdayjobs.com`) | The real posting with full text; most Israeli tech companies use Comeet or Greenhouse | Company form – best channel for automation with a final confirmation |
| **LinkedIn Jobs** | Discovery, recruiter names, who you know at the company | Easy Apply = candidate clicks (LinkedIn's terms forbid bots); many posts link to the company form – use that |
| **AllJobs**, **Drushim**, **JobMaster** | Student and junior roles, Hebrew postings, agencies | Usually needs the candidate's logged-in account → candidate clicks; some posts show an email address |
| Ads with an email address (Facebook / Telegram / WhatsApp job groups, university career centers, "שלחו קו"ח ל...") | Student positions, small companies | Email with the tailored PDF |
| **WhatsApp job groups** – exported by the candidate (Export chat → Without media) into `inbox/whatsapp/`, parsed by `tools/whatsapp_jobs.py` | Fresh student/junior posts, referrals | Usually an email address in the post |
| **Job-alert emails** (LinkedIn, AllJobs, Drushim, Glassdoor) in the candidate's inbox | LinkedIn discovery without scraping LinkedIn | Follow the link to the company's own posting |
| University career center sites and student-job newsletters | Student positions | Varies |
| Referrals ("חבר מביא חבר") | The highest interview rate of any channel | Candidate sends the referral request from `outreach.md` |

## Search patterns

Combine role × level × place. Examples:

- `site:comeet.com "Student" "Backend" Israel`
- `site:boards.greenhouse.io "Tel Aviv" "Student" developer`
- `site:jobs.lever.co Israel "Junior" Android`
- `"משרת סטודנט" פיתוח backend`, `"סטודנט/ית" "מדעי המחשב" משרה`, `דרוש/ה מפתח/ת Android ג'וניור`
- `"<target company>" careers student` – then open the company's career page

Tips:
- Job boards repost the same role; keep the company's own posting and link.
- Posting date matters: the first ~10 days get most of the attention.
- When the posting names a recruiter or team lead, record it in the job file – useful for outreach.
- Before a round, check `tracker.py list` so known jobs are not processed twice.
