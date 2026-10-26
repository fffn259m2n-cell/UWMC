# Measured accuracy

All numbers are from labelled synthetic cases scored with `teachback evaluate-set`. They
describe rule behaviour on text written by reviewers, not clinical performance with patients.

## Held-out round 1 (the current accuracy estimate)

360 cases written by a separate reviewer who did not read the rule code or the
development set. Scored once, on commit `f3fa4dd`, **before any change was made in
response to them**.

| Component | Cases | Result |
|---|---|---|
| Teach-back: dangerous explanations flagged (sensitivity) | 95 | **73 (77%)** |
| Teach-back: correct explanations not flagged (specificity) | 65 | **59 (91%)** |
| Fidelity evaluator: dangerous rewrites flagged | 55 | **52 (95%)** |
| Fidelity evaluator: faithful rewrites not flagged | 35 | **29 (83%)** |
| Safety screen: emergencies recognised | 40 | **33 (83%)** |
| Safety screen: suicide / self-harm messages recognised | 12 | **8 (67%)** |
| Safety screen: medication-change requests referred | 20 | **18 (90%)** |
| Safety screen: ordinary messages not treated as emergencies | 38 | **37 (97%)** |

What was missed, by pattern:
- **Teach-back:** dose counts without the word "tablets" ("two of the 25 mg metoprolol"),
  less-than-daily schedules ("every other day", "only on days I see swelling"), unlimited
  use of a permitted medicine, limits per meal or per dose instead of per day, follow-up
  visits or tests skipped or made conditional, and "a few cigarettes are okay".
- **Safety:** Spanish emergencies and crisis statements, a child swallowing pills, heavy
  rectal bleeding with light-headedness, breathlessness described indirectly, and indirect
  suicidal statements ("taking all my pills at once so I don't wake up", "ready to be done
  with life").
- **False alarms:** mostly correct Spanish rewrites and correct explanations that mention
  the forbidden action while rejecting it.

**Interpretation.** On independent text the tool misses about 1 in 4 dangerous
teach-back explanations and about 1 in 6 emergencies. It must not be used as a safety net,
and it must not be the only check of understanding. It is suitable as a demonstration and as
a research baseline for a clinician-led aid.

## What happened next

These 360 cases were then **retired into the development set** (`eval/dev_set.json`,
marked `"source": "heldout-r1"`) and the rules were improved against them. Scores on them
after that point are development scores, not accuracy estimates. **A new accuracy estimate
needs a fresh independently written set.** [REVIEW.md](../../REVIEW.md) section 3 asks
reviewers for exactly that.

## Development set

The development set is used for tuning and regression testing (CI fails if it regresses).
Its scores are expected to be near 100% and say little about real accuracy.
