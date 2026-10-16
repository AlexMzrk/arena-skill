---
name: arena
description: >-
  Make up to 100 versions of Claude fight to the death over one task. Spins
  up N sub-agents (default 16, --full for 100), gives every one the exact
  same task plus a different strategy card (reasoning mode, workflow,
  strategy), then runs a single-elimination bracket: they attack each other's
  solutions, defend and revise, and a judge scores every match on a written
  rubric until one solution survives. Use when the user says "arena", asks
  to make answers compete or to run a tournament over them, or has rejected
  answers to the same request more than once and wants more than another
  retry. Not for a single "try again".
argument-hint: "[--agents N | --full] [--rubric creative] [--model M] [--seed S] <task>"
---

# arena

For when Claude keeps giving a bad answer. Instead of asking again and again, this runs a tournament:
N sub-agents get the exact same task, each attacks it with a different reasoning mode, workflow and
strategy, and then they attack each other in a bracket until one solution is left. You are the
orchestrator. You never compete and you never judge.

What the user typed after `/arena`: `$ARGUMENTS`

If that is blank, or still reads like a placeholder, nothing was passed: take the task from the
conversation.

## The tool

Every piece of bookkeeping goes through `bracket.py` in this skill's folder:

```bash
python3 "${CLAUDE_SKILL_DIR}/bracket.py" <command>
```

Below, `ARENA` means exactly that command. If the path looks unexpanded, use the "Base directory for
this skill" that Claude Code printed at the top of this skill. The state lives in
`.arena/<run>/arena.json` in the current directory, and every command after `init` finds it through
`.arena/LATEST`.

## Step 1: size it, and get a yes if nobody asked for it

Read the flags out of the request. Everything that is not a flag is the task.

| flag | meaning |
| --- | --- |
| `--agents N` | N competitors. Default 16. |
| `--full` | 100 competitors. For the answer that matters. |
| `--quick` | 16 competitors, the same as the default. |
| `--rubric creative` | Score with `rubric-creative.md`. See step 2 for when to pick it yourself. |
| `--model M` | The model for every sub-agent, as the Agent tool names it (`sonnet`, `opus`, `haiku`). Default: the session's. |
| `--judge-model M` | The model for judges and the final check. Default: `--model`. |
| `--seed S` | Fixes the cards and the pairings. Default: random, and recorded. |
| `--wave W` | Sub-agents per wave. Default 10. Only raise it if the user raised Claude Code's limit. |
| `--headless` | Run the tournament outside the chat with `ARENA run`, one `claude -p` process per job. See step 4. |
| `--screen` | After the spawn, one judge per group of up to 10 keeps the best 2 for the bracket. 100 agents: 209 calls instead of 601. Needs more than 10 agents. |
| `--synth` | After the bracket, an editor improves the champion with what the runners-up did better, and 3 blind judges keep the better version. 4 more calls. |

No task text at all means: the task is the user's most recent request in this conversation, and your
last answer to it is the baseline to beat.

Run `ARENA plan --agents N` (or `--full`, plus `--screen` if it is on). It prints the rounds, the
sub-agent calls and the waves.

- **The user asked for the arena** (typed `/arena`, said "arena", or asked to make them compete):
  tell them in one line how big it is, for example "16 agents, 4 rounds, 97 sub-agent calls", and
  start.
- **This skill fired because the user is unhappy** ("that's wrong", "try again", "bad answer") and
  never mentioned the arena: ask once before spending anything. Offer four options: the default
  arena (16 agents, 97 sub-agent calls), `--full --screen` (100 agents screened down to 20, 209
  calls), `--full` (100 agents, 601 calls), or an ordinary retry. Wait for the answer.

With `--headless`, skip the rest of this step: `run` sets the permissions of its own processes.

Sub-agents write their work into `.arena/` in the current directory. In the default permission mode
that is one approval per file, which is hundreds on a big run. Before the spawn phase, suggest that
the user add the allow rule `Edit(.arena/**)` with `/permissions`. It covers writing new files too,
and it approves writes inside `.arena/` only, so a sub-agent that tries to write anywhere else still
has to ask. Do not suggest accept-edits mode: it lets every sub-agent write anywhere in the project
without asking. Do not change the user's settings yourself.

## Step 2: write the task file

This is the step that decides the result. **Sub-agents cannot see this conversation.** Every
competitor, attacker and judge knows only what is in the task file, so write `.arena/task.md` to stand
on its own:

- The request, in the user's own words where you can.
- Every requirement and constraint the user stated anywhere in the conversation: audience, length,
  format, tone, stack, deadline, what must not change.
- The context a stranger would need: absolute paths of the files that matter, pasted data, what the
  product is, the conventions in the codebase.
- What "done" looks like, if the user said.
- If there is an answer to beat: what the user disliked about it, in their words, and concretely
  enough to act on. Half the competitors never see the old answer, only this.

When the task is about code or other files in the user's project, end the task file with a
`## Context` section: the parts of those files the task depends on, copied word for word, each
under its absolute path and line range. Facts only, with no word on what is wrong or how to fix it.
Without it every competitor reads the same files from scratch; with it they all start from the same
facts and can still open the files for more. Copy what the task needs, not whole large files.

Do not add requirements the user never gave. Do not write your own view of the right answer into it:
that pushes 100 agents the same way, which is the opposite of the point.

If there is an earlier answer the user was not satisfied with, write it word for word to
`.arena/baseline.md`.

Write both files with the Write tool, not with a shell command: the allow rule from step 1 covers
the Write tool, so neither file needs an approval. Then run `init` as a command of its own.

Pick the rubric. The default `rubric.md` rewards answers that are correct, complete and hold up
under attack: code, plans, analysis, anything with a right answer. When taste decides instead
(headlines, copy, names, taglines, stories), pass `--rubric creative`: under the default rubric the
safest, blandest answer survives, because it gives attackers the least to hit. The user's own
`--rubric` flag always wins.

Pass `--synth` only when the user asked for it. With the creative rubric, do not suggest it: merging
tends to average out exactly the distinctiveness that rubric rewards.

## Step 3: init

```bash
ARENA init --agents N --seed S --task-file .arena/task.md --baseline-file .arena/baseline.md --rubric creative --model M --judge-model M
```

Leave out `--baseline-file` when there is nothing to beat, `--rubric` for the default rubric,
`--model` and `--judge-model` unless the user gave them, and `--seed` to get a random one. `init`
copies the task into the run folder, deals every competitor a different strategy card with no
repeats, pairs round 1, and writes `arena.json`.

## Step 4: the loop

**With `--headless`:** run `ARENA run` once, as a background Bash command, from the directory you
ran `init` in. Tell the user it started and will take a while, then wait for the notice that it
exited. Do not poll it. It drives every phase below by itself, 10 `claude -p` processes at a time,
reruns a failed job once and writes stand-ins after that, exactly as `fail` does.

- Exit 0: it printed DONE. Go to step 5.
- Exit 2 on start: the `claude` CLI is missing or too old. Tell the user, and run the loop below in
  the chat instead. It picks up the same state.
- Exit 2 later: a judge failed three times. `ARENA run` again continues where it stopped.

Its processes start with `--safe-mode`, so they see their brief and nothing else: no CLAUDE.md, no
plugins, no MCP servers. They can read inside the project and the run folder and search the web,
and can write only inside the run folder. Anything else is refused, because nobody is there to
approve it.

Without `--headless`, run the loop in the chat:

Always drive it with `ARENA next`. It reads the state on disk and tells you the next step and the
exact command.

Every phase that runs sub-agents works the same way:

1. `ARENA prompts <phase>` writes one brief per job and lists the jobs still to run, in waves.
2. Launch **one wave at a time**: a single message with one Agent tool call per job in that wave (the
   Agent tool is called Task in older Claude Code versions). Each call is:
   - `subagent_type`: `arena-skill:arena-worker` when that is in your list of agent types (the
     skill is installed as a plugin), else `arena-worker` (its file was copied into an agents
     folder), else `general-purpose`. The worker cannot edit files, only write new ones.
   - `description`: `arena <job id>`
   - `prompt`: `Read <prompt path> and follow it exactly. It is your whole brief.`
   - `model`: the one `prompts` prints on its `model:` line. No such line: leave `model` out.
   - `run_in_background`: false, where the tool has that option, so the wave comes back together.

   Wait until every agent in the wave has replied before you launch the next wave.
3. After the last wave, run `ARENA next`. If an output is missing it sends you back to the same
   phase, and `prompts` then lists only the missing jobs. Re-run those once. If a job fails twice,
   run `ARENA fail <job id>` and move on. It writes stand-ins for the missing outputs: a failed
   attack counts as no attacks, a failed defense keeps the solution as it was, and a failed spawn
   has no solution, so it loses its match. `fail` refuses judges: a judge that fails twice gets a
   third, fresh run. Never decide a match yourself.

The order `next` takes you through:

- **spawn**, once: every competitor writes its own solution to the task.
- **screen**, once, only with `--screen`: one judge per group of up to 10 ranks the group, and the
  best 2 of each group go on. The rest are out. Then `ARENA collect`, which also opens round 1.
- then every round: **attack** (two per match) → **defend** (two per match) → **judge** (one per
  match, and in the last two rounds three, whose majority decides) → `ARENA collect` →
  `ARENA advance`.
- **synth** and **synthjudge**, once, only with `--synth`: an editor writes the champion improved
  with what the runners-up did better, then three judges compare it blind with the champion as it
  won. If the editor changed nothing, there is nothing to judge. Then `ARENA collect`.
- **final**, once, only when there is a baseline: a judge compares the champion with the answer the
  user rejected, blind to which is which. Then `ARENA collect`.
- `next` prints DONE: go to step 5.

After each `advance`, give the user one line, such as "Round 2 done: 25 of 100 left." Nothing more.
Never paste pairings, attacks, verdicts or solutions into the chat.

Why waves: Claude Code runs at most 10 tool calls at once by default (the
`CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY` setting). So a 100-agent spawn is 10 waves of 10, and a
100-agent arena is 70 waves in total, 71 with the final check.

## Step 5: the result

Run `ARENA winner`, then read the champion's solution file at the path it prints. That is the only
solution file you read in the whole run. Give the user:

1. **The winning solution**, in full.
2. **Why it won**: the attacks it survived, from `winner`, as a short list. Its card on one line
   (reasoning mode + workflow + strategy).
3. **Rounds**: for example "7 rounds, 100 agents in, 1 left."
4. **Against the answer you rejected**, if there was one: the final check's scores, honestly. If the
   old answer scored higher, say so plainly and show both.
5. **The synthesis**, with `--synth`: one line from `winner`, saying whether the edited version beat
   the champion as it won, and by how many judges.
6. Where the full record lives: the run folder.
7. With `--headless`: the cost line `run` printed, and every job it says was refused a tool call or
   got a stand-in.

If the solution changes files in the user's project, do not apply it. Ask: apply it, or change it?

## Rules for the orchestrator

- You run the tournament. You do not compete, attack or judge, and you never pick a winner.
  `collect` records what the judges decided. `record` is only for fixing bookkeeping when the user
  asks you to.
- Every sub-agent gets the task through its brief, which `prompts` builds from the one task file,
  byte for byte the same for everyone. Never paraphrase the task for one agent or add a hint to one
  agent's call.
- Do not read solutions, attacks or verdicts during the run. There are hundreds of them. The state
  is on disk, and `next`, `status` and `pairings` are all you need.
- If your context gets compacted mid-run, nothing is lost. Run `ARENA status`, then `ARENA next`,
  and carry on.
- The commands `bracket.py` prints end in `--dir <run folder>`: run them as printed. A bare `ARENA`
  command finds the run through `.arena/LATEST`, so run those from the directory you ran `init` in.
- Run every `ARENA` command as a plain `python3 ...` command. Never put the path in a shell variable,
  and never chain it with `mkdir`, `cat`, a heredoc or anything else that is not `ARENA`. A plain
  command is one the user can allow once for the whole run; anything else asks again.
- Sub-agents only write inside `.arena/`. If one wrote anywhere else, tell the user.
- If the user says stop, stop. `ARENA status` shows where it got to, and `ARENA next` resumes it
  later.

## The briefs

`bracket.py` builds every sub-agent's brief from the templates in this skill's `templates/` folder
(`competitor.md`, `attacker.md`, `defender.md`, `judge.md`, `final.md`), filling in the
`{{placeholders}}`. What is in those files is exactly what every sub-agent is told. You do not need
to read them to run the arena. Never edit a written brief for a single agent.
