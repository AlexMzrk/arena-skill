# The arena rubric: creative

For tasks where taste decides: headlines, copy, names, taglines, pitches, stories. The arena uses it
when `init` gets `--rubric creative`. Every match is then scored against this page. The judge scores
both solutions, `bracket.py` does the arithmetic, and the higher weighted total goes through. The
loser is out.

## The five criteria

Each criterion is scored 0 to 10. The weight is how much of the 100-point total it is worth.
`bracket.py` reads the names and weights from this table, so change them here.

| criterion | weight | the question |
| --- | --- | --- |
| Fit | 30 | Does it do exactly what the brief asks? Audience, length, format, tone and every hard constraint the task states. |
| Impact | 25 | Would it work on the people it is for: make them stop, feel, remember or act? |
| Distinctiveness | 20 | Could only this answer have been written for this task, or would it fit anyone's? |
| Robustness | 15 | Does it hold up against every attack raised in this match that applies to it: broken constraints, false claims, ways the audience would misread it? |
| Clarity | 10 | Does the audience get it at first read, with nothing to decode? |

Weighted total = (fit x 30 + impact x 25 + distinctiveness x 20 + robustness x 15 + clarity x 10) / 10.
That gives a number from 0 to 100.

## Anchors

Use the whole scale. A 7 is not a polite default.

**Fit**
- 10: every stated requirement is met: audience, length, format, tone.
- 7: all are met, one is stretched.
- 4: a stated requirement is missed.
- 0 to 2: it answers a different brief.

**Impact**
- 10: the audience would still remember it tomorrow.
- 7: it works, but it will not be remembered.
- 4: correct and forgettable.
- 0 to 2: it would put the audience off.

**Distinctiveness**
- 10: it could only have been written for this brief.
- 7: a fresh angle on a familiar idea.
- 4: the first idea anyone would have.
- 0 to 2: a cliche, or a template with the product name dropped in.

**Robustness**
- 10: every attack in this match that applies to it is fixed or correctly rebutted, and nothing new is broken.
- 7: one MINOR attack still standing.
- 4: a MAJOR attack still standing, or a fix that broke something else.
- 0 to 2: a FATAL attack still standing.

An attack aimed at one side also counts against the other wherever it applies there. A missing
attack file means the opponent raised nothing. Score robustness on the attacks that apply and the
flaws you found yourself. Taste is not an attack: "I would have said it differently" is not a flaw.

**Clarity**
- 10: understood at first read.
- 7: one phrase needs a second look.
- 4: the reader has to work out what it means.
- 0 to 2: lost on the audience.

## The fatal rule

Mark a solution `fatal` only when you have verified a flaw that makes it unusable for the brief: a
hard constraint broken (length, format, a word it must or must not use), a false claim about the
product, or something the audience would read as offensive. A fatal solution cannot beat a solution
that is not fatal, whatever the totals say. If both are fatal, the totals decide.

## Ties

There are no draws. On an exact tie, the solution with fewer attacks still standing wins. If that is
also level, the higher fit score wins. If that is also level, pick the one you would hand to the
user, and say why in the reason.

## What the judge does not reward

- **Safety for its own sake.** An answer nobody can attack because it says nothing is not robust, it
  is weak. Score it low on impact and distinctiveness.
- **Length.** Longer is not better. Most creative briefs reward fewer words.
- **Confidence.** A defense that says "fixed" is not proof. Check the revised solution.
- **The approach.** The judge never sees the strategy cards and does not guess at them. It scores
  the work, not the method that produced it.
- **Talking about quality.** "This bold, memorable line" earns nothing. The line has to be bold and
  memorable.
- **Agreement with the judge's own taste** where the brief does not ask for it. Score what the brief
  and its audience want.
