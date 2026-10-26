<!--
COVER LETTER TEMPLATE – copy into the application folder as cover_letter.md and replace every {{...}}.
Rules
* 200–350 words, 4 short paragraphs, one page. Language: the language of the job ad.
* Never claim eligibility the facts do not support (time left in the degree, hours, location, clearance).
* Every claim must come from master_resume.md – no invented skills, numbers or experience.
* Mirror 3–5 exact keywords from the job description (same spelling as the ad).
* One concrete detail about the company (product, domain, tech, recent news) beats three adjectives.
* Avoid clichés: "I am writing to apply for...", "hard-working team player", "passionate about technology".
Build the PDF:  python3 tools/build_pdf.py <folder>/cover_letter.md
-->

# {{Full Name}}

**{{Headline matching the role, e.g. Junior Backend Developer}}**

{{Phone}} · [{{email}}](mailto:{{email}}) · [github.com/{{user}}](https://github.com/{{user}}) · [linkedin.com/in/{{user}}](https://www.linkedin.com/in/{{user}}/)

{{Date, e.g. October 26, 2026}}

{{Hiring manager name, or "Hiring Team"}}<br>{{Company}} – {{Role title}}

Dear {{Hiring manager name / Hiring Team}},

<!-- P1 HOOK (2–3 sentences): the exact role title + why THIS company (one concrete detail) + a one-line value
proposition built from the top 2 requirements. -->
{{Paragraph 1}}

<!-- P2 PROOF #1 (3–4 sentences): the project or job that best matches requirement #1. What was built, the stack
(JD keywords), the candidate's part, one concrete number or result from the master resume. -->
{{Paragraph 2}}

<!-- P3 PROOF #2 + DIFFERENTIATOR (3–4 sentences): requirement #2 from another project, then what makes the candidate
different (e.g. teaching, leadership, military responsibility, a rare domain combination) – tied to the role. -->
{{Paragraph 3}}

<!-- P4 CLOSE (2 sentences): availability (start date / weekly hours for student roles) + a confident call to action. -->
{{Paragraph 4}}

Best regards,<br>{{Full Name}}
