# Scratchpad

Working notes, split by topic so a session reads only what its task needs.
Start every session with `status.md`. Read the others only when the "Read it
when" column says so.

| File | What's in it | Read it when |
|---|---|---|
| [status.md](status.md) | Current phase, who's on what, what's waiting on whom | Always, at the start of a session |
| [backlog.md](backlog.md) | Open work only, in priority order, with an owner per item | Picking or starting a task |
| [lessons.md](lessons.md) | Save format, combat formulas, engine bookkeeping gotchas | Before changing `engine/` or `verify/state_v123.py`, or when a replay mismatch looks familiar |
| [investigations/](investigations/) | One file per open mismatch hunt: symptom, what's been tried, next step | Picking up or continuing a hunt |

Rules and their evidence are **not** kept here. They live in
`verify/ledger.json` and `data/conflicts_and_gaps.md`, as before.

## One task per chat

Each conversation re-sends everything said in it on every message, so a long
chat gets more expensive with every turn. To keep chats short:

1. Start a fresh chat for each task. Read `status.md` and the task's backlog item.
2. During a long task, especially a mismatch hunt, write progress into the
   investigation file before the chat gets heavy. Then the person clears the
   chat and continues in a new one with "continue investigations/<file>".
3. Finish by closing the item (below), running `sh scripts/check.sh`, and
   committing. Then start the next task in a new chat.

Don't dump large files into the chat. Query save JSONs and the notebook with
small scripts that print only what's needed.

## Closing work

When something closes, it leaves `backlog.md`:

- **Done** → delete the item. Git already records what shipped.
- **A rule settled** → `verify/ledger.json` and `data/conflicts_and_gaps.md`,
  in the same change (the evidence rules in `CLAUDE.md`).
- **A gotcha worth remembering** → `lessons.md`.
- **An investigation finished** → its conclusion goes to one of the above, then
  delete the file.

The test for what belongs here: **would git or the ledger tell me this?** If
yes, leave it out. No session logs.

## Keep it small

`status.md` and `backlog.md` are read at the start of every session, so keep
each to about one screen. If one grows, cut what's closed or move detail into
an investigation file.
