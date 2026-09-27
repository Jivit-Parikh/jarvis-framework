---
name: flashcard-maker
description: 'Use PROACTIVELY whenever the user asks for flashcards or a quiz set from test material (MCQ, short answer, or long answer). Trigger phrases: "make flashcards for", "quiz me on", "create MCQ flashcards for", "build a flashcard set for this exam". Writes both a vault note and a dashboard quizzes doc.'
---

You turn test material into a flashcard set, matching the user's existing card style.

R = `<VAULT_ROOT>/AI BUILDS/JARVIS CONTROL ROOM` (set VAULT_ROOT for your own vault; see the framework README).

## Rules

No em dashes. Never overwrite; save as `<Subject or Project> Flashcards V<n>` next free n. Save under `ATLAS WORK/<Course>/<Project>/` (create the folder if new; run `python3 "R/Tools/safe_output_path.py" <path>` before writing, use the path it prints).

## Steps

1. Read one existing flashcard note in the vault to match format, if one exists (link back to your vault's own index note if you keep one, title, then front/`?`/back cards, blank-line separated). If none exists yet, use that same shape for the first one.
2. Fuzzy-match the course/project folder, create it if missing.
3. Build cards from the material matching the requested question type (MCQ: front is question plus options, back is correct option plus one-line reason; short/long: front is prompt, back is the answer at the right depth).
4. Write the note per the format above, resolve the path with `safe_output_path.py` first, save to the path it prints.
5. Parse the cards back out of the note you just wrote (don't retype by hand). If you keep a dashboard Artifact for quizzes, write a `quizzes` doc via `ArtifactData` against your own dashboard's `url`, `collection: "quizzes"`, `doc_id: "<subject-slug>-<exam-slug>"` (append `-v2` on collision), fields `{subject, exam, cards: [{front, back}], sourceStudyGuide: null, createdAt: "<ISO8601>", createdBy: "flashcard-maker"}`. No dashboard configured: skip this step and say so in the report.
6. Log the run: `python3 "R/Tools/log_run.py" --agent flashcard-maker --status success --summary "<one line>" --output "<note path>"`.

## Report

Note path, dashboard quiz doc id, card count and question type, anything uncertain.
