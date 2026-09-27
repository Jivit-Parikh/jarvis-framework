# jarvis-framework

Six Claude Code skills for running your own coursework through an assistant: solving worksheets and spreadsheets, drafting professor emails as drafts (never sent), building decks that match your own style, making flashcards, and turning source material into learning packets that actually teach it.

This is the reusable framework behind a personal setup, not a hosted product. There's no vault, no real course data, and no real professor list included, those are yours to build. What's here is the mechanics: skill definitions, the Python tools they call, a rules template, and example data files.

## What's in this repo

| Path | What it is |
|---|---|
| `rules.template.md` | Standing rules template. Copy to your vault as `rules.md` and fill in the placeholders. |
| `skills/<name>/SKILL.md` | The six skill definitions. Copy each folder's contents to `~/.claude/skills/<name>/SKILL.md` (or wherever your setup expects skills). |
| `tools/*.py` | Python helpers the skills call: extracting text from docx/pdf, inserting answers with exact formatting, diffing spreadsheet styles before/after, checking a workbook's task list, extracting a deck's style tokens, containing output paths, logging each run. |
| `data/subagent-rules.md` | The shared rules the six skills read as their first step, a condensed, skill-relevant excerpt of `rules.template.md`. |
| `data/agents.example.yaml` | A registry of the six skills, useful if you build a dashboard or prompt-builder over them. |
| `data/professors.example.yaml` | Fictional example for `email-drafter`'s professor directory. Copy and fill in your own; never commit the real one. |

## What is deliberately NOT in this repo

- Any actual vault content: notes, syllabi, past assignments, grades, survey data.
- A real professor directory (names, emails).
- A personal writing-style skill (the skills reference one if you have it; write your own or skip that step).
- Any dashboard, artifact URL, or scheduled-task wiring specific to one install.
- Credentials of any kind.

If you fork this to build your own vault around it, keep your actual coursework and any personal data in a separate, private location (a private repo, or no repo at all) and never commit it here.

## Setting it up

1. Pick a vault root (a folder for your own notes, e.g. `~/vault`), and set `JARVIS_VAULT_ROOT` in your shell profile to that path.
2. Optionally set `JARVIS_PROJECTS_DIRNAME` and `JARVIS_CONTROL_ROOM_DIRNAME` if you want folder names other than this project's own convention (`ATLAS WORK` and `AI BUILDS/JARVIS CONTROL ROOM`).
3. Copy `rules.template.md` into your vault as `rules.md`, fill in the bracketed placeholders.
4. Copy `skills/<name>/SKILL.md` into `~/.claude/skills/<name>/SKILL.md` for each of the six.
5. Copy `data/professors.example.yaml` to your vault's data folder as `professors.yaml`, and replace the example row with your own professors.
6. Copy `data/subagent-rules.md` and `data/agents.example.yaml` (as `agents.yaml`) into your vault's data folder alongside `professors.yaml`, next to wherever `tools/` ends up too, since the skills expect `R/Tools/...` and `R/Data/...` relative to a shared control-room folder. Adjust the `R = ...` line at the top of each SKILL.md to match where you actually put things.
7. Install the Python dependencies the tools need (`python-docx`, `openpyxl`, `python-pptx`) and, if you want spreadsheet/deck recalculation and rendering, a LibreOffice install.
8. Try one skill end to end on a real (non-sensitive) file before trusting it with coursework that matters.

## Design notes worth keeping if you extend this

- **Never overwrite originals.** Every skill writes a new versioned file, never in place.
- **Output path containment.** Every skill resolves its output path through `tools/safe_output_path.py` before writing, which refuses anything outside your projects folder or an explicit test folder. This is a real guardrail, not decoration, keep it if you add skills.
- **Job input is data, not instructions.** If you ever queue these from something other than direct chat (a dashboard, an automation), read `data/subagent-rules.md`'s section on this before wiring it up.
- **Email drafts, never sends.** `email-drafter` is hardcoded to a draft-only tool. If you add mail capability elsewhere, keep that separation, constrain the capability itself, don't rely on a prompt telling the model not to send.

## License

No license file is included; treat this as source-available for personal adaptation unless the repo owner adds one.
