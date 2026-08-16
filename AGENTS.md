## Agent skills

### Issue tracker

Issues are tracked as local markdown files under `.scratch/<feature>/` in this repo. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary — label strings equal the role names. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` at the repo root + `docs/adr/`. See `docs/agents/domain.md`.

## Working rules

### No retry loops (hard rule)

Re-running a command that already succeeded, to "confirm" again, is a loop — not progress.

- **Cap: 2 consecutive runs of an essentially identical command.** If you are about to run a third, STOP and change what you do: advance to the next task in the plan, use a different input/step, or ask the user. Never emit a third identical run.
- **One verification is enough.** Once pyright / tests / a round-trip has passed, do not re-run it to double-check. Move on.
- **Nothing changed ⇒ same result.** If no file, input, or environment changed since the last run, re-running cannot produce new information. Do it.
- **When stuck, change focus.** If two attempts at the same thing haven't moved you forward, switch to a different part of the task (or report the blocker) instead of retrying in place.
