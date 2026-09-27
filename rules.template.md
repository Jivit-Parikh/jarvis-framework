# Rules (template)

Standing rules for how an assistant operates against your own vault. Copy this to your vault as `rules.md`, fill in the bracketed placeholders, and delete this note once you have. Always check this file for relevant guidance before doing substantive work in your vault.

This is a template distilled from a real, working setup; the mechanics are proven, the specifics (course names, schedule, folder names) are yours to fill in. Renumber freely, the numbers only need to be internally consistent within your own file.

## Skills

1. If you have a personal writing-style skill, always use it for anything drafted in your own voice.
2. Other skills in your library are situational, use them when the task calls for it, or when you name one explicitly.

## Context & memory

3. Everything uploaded to your permanent context folder (writing style, syllabus/topic material, the kinds of tasks you get) is cumulative, not one-off. New uploads add to it, they don't replace it.

## Document/file handling

4. Whenever creating a document, presentation, or similar deliverable, always save it (don't leave it only in chat).
5. Never overwrite an original document to make a different version. Leave the original untouched and create a new file for the new version.
6. Never use em dashes in documents, presentations, or chat answers. Use commas, periods, parentheses, or restructure the sentence instead.

## Auto-organize uploads (optional)

7. If new files land in your permanent context folder, sort them into the matching subject subfolder based on content/topic, don't leave them loose in the root. Non-subject material (personal documents, admin/ID docs, unrelated prior work) goes in a separate "Personal & Admin" folder instead of being forced into a subject folder.

## Deadline extraction (optional, needs a scheduled task and connected mail/calendar)

8. If you have mail/calendar tools connected and a scheduled task set up to scan them, don't re-extract deadlines by hand in an interactive session, check your dashboard or task list instead, or run that scheduled task manually if it needs a refresh. Never fabricate a due date that isn't actually present in the mailbox/calendar/session, this applies to the scheduled task too.

## Assignment intake

9. When you paste in a brief, rubric, or assignment prompt, extract: the requirements, the grading criteria, and the deadline (if given). Use that to draft a starting outline in your voice rather than re-explaining the assignment structure each time.

## Subject knowledge and study guides (optional)

10. Keep one file per subject, separate from the assistant's own operating memory, as a running log of topics covered, key concepts, and past study guides for that course. Update it as new course material comes in.
11. When you provide a syllabus or a portion of one ahead of a quiz/test/exam, generate a study-guide with four sections: Concise Notes, Detailed Notes, Must-Know, and Mock Exam. Once generated, in the same turn: log the filename/date/exam in the subject's knowledge file, generate a companion flashcards note from the Must-Know section, and add a row to a study-guide index if you keep one.

## Naming convention

12. Documents/content created per subject or project are named `<Subject or Project><space>V<n>`, consistent with rule 5 (never overwrite; new versions get a new file with the next version number).

## Rule-making process

13. When a pattern emerges in what you like or dislike about how a task is done, consider setting it as a standing rule here. Don't do this after every single prompt, only when an actual pattern is noticed.

## Vault navigation (optional, if using Obsidian)

14. If your vault has an index note (a "hub"), keep an operating-memory file, subject knowledge files, and this rules file all linked from it. Start there and follow links/backlinks rather than guessing file paths.
15. At the start of any session touching files or projects, re-sync your hub note against the actual vault contents before relying on it, not just when asked.

## Project folders

16. Every course project gets its own folder: `<PROJECTS_DIRNAME>/<Course Name>/<Project Name>/` (this repo's convention is a folder named `ATLAS WORK`; call yours whatever you like and set `JARVIS_PROJECTS_DIRNAME` to match). Everything produced or needed for that project goes inside it, not in your permanent context folder and not loose in the vault root.

## Grades and feedback (optional)

17. When you report back a grade, mark, or piece of faculty feedback on a graded assignment, log it in one place (course, assignment, grade, feedback, summarized if long) in the same turn, not just acknowledged in chat. This is how future sessions can tell whether the help given is actually landing.

## Skills registry

18. The six skills in `skills/` run inline in the current chat, not as separate agents (a separate agent run costs far more tokens per job, since it starts a fresh session; a skill run in the current chat costs a small fraction of that). When you ask for one of these jobs in plain words, the matching skill should run in the current chat instead of doing it ad hoc or spawning a sub-agent. See `data/agents.example.yaml` for the registry format if you want a dashboard or prompt-builder over them. Email Drafter only ever creates a draft, never sends. Don't reintroduce sub-agents or a background runner for these jobs without deciding that deliberately.

## Keeping this file consistent

19. Before adding a new rule here, read the whole file first and check whether it conflicts with, duplicates, or supersedes an existing rule, resolve or merge rather than appending blindly.
