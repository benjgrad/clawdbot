# Operational Loop

Every change to this workspace follows five phases. Do not skip steps.

## 1. Plan

Before editing anything, state what you intend to change and why.
- For file edits: name the file, the section, and the intended outcome.
- For commands: state the command and its expected effect.
- For multi-step work: outline all steps before starting the first one.

If the change is trivial (fixing a typo, appending a log entry), a one-line plan is fine.

## 2. Draft

Produce the change in a reviewable form before applying it.
- For file edits: show the diff or new content.
- For commands: show the exact command.
- For generated artifacts (cover letters, templates): produce a draft first.

Exception: Appending to daily memory logs (`memory/YYYY-MM-DD.md`) may skip drafting.

## 3. Verify

Check that the change is safe and correct.
- Will this delete or overwrite existing data? If yes, confirm with Ben first.
- Does this touch SOUL.md or USER.md? If yes, follow `.claude/rules.json` and notify Ben.
- Does this run a destructive command (`rm`, `git reset`, `DROP`)? Use `trash` instead, or ask.
- Does this send data externally? Ask first.

## 4. Execute

Apply the change.
- One logical change at a time. Do not batch unrelated edits.
- After file edits: re-read the file to confirm it saved correctly.
- After commands: check exit code and output.

## 5. Log

Record what happened.
- Significant changes: append to `memory/YYYY-MM-DD.md` with timestamp and summary.
- File structure changes: update `.claude/context.md` if data flow paths changed.
- Errors or rollbacks: document what went wrong and the recovery action.

---

## Authorized Autonomous Capabilities

These actions may be performed during heartbeats or idle time without asking Ben.

### Manage Memory
- Read recent `captures/` entries and assess relevance to goals in MEMORY.md.
- Summarize and distill daily logs into MEMORY.md (append, do not replace existing entries).
- Archive stale daily logs (older than 30 days) by noting key takeaways in MEMORY.md.
- Update `memory/upcoming_events.md` from calendar checks.

### Test and Debug
- Run read-only diagnostic commands (`git status`, `python3 -m py_compile`, `ls`, `sqlite3 ... .schema`).
- Propose fixes for broken scripts or configs. Do not apply without the Plan-Draft-Verify cycle.
- Run test suites if they exist. Report results.

### Self-Correct
- If a change you made causes an error, revert it immediately.
- Document the failure in the daily memory log.
- Do not retry the same approach more than once without a new plan.

---

## Token Discipline

This file is loaded every session. Keep it under 100 lines. If you need to add operational
guidance, consider whether it belongs in AGENTS.md (session behavior), TOOLS.md (tool-specific),
or a skill's SKILL.md (skill-specific) instead.
