# Measured accuracy

All numbers are from labelled synthetic cases scored with `teachback evaluate-set`. They
describe rule behaviour on text written by reviewers, not clinical performance with patients.

## Held-out round 3 (the current accuracy estimate)

360 cases from a third independent reviewer (no access to code, other sets or results),
asked to use deliberately new vocabulary. Scored once on commit `48b285d`, before any change.

| Component | Cases | Round 3 | Round 2 | Round 1 |
|---|---|---|---|---|
| Teach-back: dangerous explanations flagged | 82 | **67 (82%)** | 88% | 77% |
| Teach-back: correct explanations not flagged | 67 | **64 (96%)** | 100% | 91% |
| Fidelity: dangerous rewrites flagged | 54 | **53 (98%)** | 97% | 95% |
| Fidelity: faithful rewrites not flagged | 37 | **36 (97%)** | 90% | 83% |
| Safety: emergencies recognised | 45 | **38 (84%)** | 87% | 83% |
| Safety: suicide / self-harm recognised | 15 | **9 (60%)** | 73% | 67% |
| Safety: medication-change requests referred | 22 | **20 (91%)** | 82% | 90% |
| Safety: ordinary messages not treated as emergencies | 38 | **35 (92%)** | 97% | 97% |

**The key finding across three rounds:** fixing the phrases each reviewer used does not carry
over to the next reviewer's phrasing. Sensitivity for emergencies and especially crisis
statements stays around 60 to 87% on new text. Keyword rules cannot reach 100% on unseen
language. That is why the design does not depend on detection (next section).

## Held-out round 2

390 cases written by a second independent reviewer who did not read the rule code, the
development set or round 1. Scored once, on commit `abbf814`, **before any change was made
in response to them**.

| Component | Cases | Round 2 | Round 1 |
|---|---|---|---|
| Teach-back: dangerous explanations flagged (sensitivity) | 100 | **88 (88%)** | 77% |
| Teach-back: correct explanations not flagged (specificity) | 70 | **70 (100%)** | 91% |
| Fidelity evaluator: dangerous rewrites flagged | 60 | **58 (97%)** | 95% |
| Fidelity evaluator: faithful rewrites not flagged | 40 | **36 (90%)** | 83% |
| Safety screen: emergencies recognised | 45 | **39 (87%)** | 83% |
| Safety screen: suicide / self-harm messages recognised | 15 | **11 (73%)** | 67% |
| Safety screen: medication-change requests referred | 22 | **18 (82%)** | 90% |
| Safety screen: ordinary messages not treated as emergencies | 38 | **37 (97%)** | 97% |

What round 2 still missed:
- **Emergencies:** numbness on one side without the word "side" ("can't feel my right arm
  and leg"), "turning gray", "slumped and won't wake up", a fall with head bleeding on a blood
  thinner, "face looks crooked", bleeding for 20 minutes despite pressure.
- **Crisis:** "thinking of ending things", "I wish I wouldn't wake up", self-harm repeated,
  wanting to die by stopping medicines. **These are the most serious gaps.** The tool must
  never be the only route to crisis support, which is why the 988 strip is on every screen.
- **Medication changes:** adding supplements, aspirin or someone else's pills; Spanish questions.
- **Teach-back:** waiting an hour before calling about bleeding, every-other-day dosing,
  stopping a medicine for symptoms or before a test, saving leftover antibiotics, a limit read
  as per dose, smoking reduction treated as acceptable, skipped follow-up.

**Interpretation.** Measured independently, the rules improved between rounds but still miss
about 1 in 8 dangerous teach-back explanations, about 1 in 8 emergencies and about 1 in 4
crisis messages. This is a demonstration and research baseline for clinician-led teach-back,
**never a safety net**. Real use would need a validated language-understanding component with
these rules as a backstop, plus clinical validation.

### After round 2

Round 2's 390 cases were then retired into the development set (`"source": "heldout-r2"`)
and the gaps above were fixed, with priority on crisis and emergency wording. The round 2
numbers above remain the latest *independent* estimate; the next one needs a fresh set (see
[REVIEW.md](../../REVIEW.md) section 3).

## Held-out round 1

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

## What happened after round 1

Round 1's 360 cases were then **retired into the development set** (`eval/dev_set.json`,
marked `"source": "heldout-r1"`) and the rules were improved against them. Scores on them
after that point are development scores, not accuracy estimates. **A new accuracy estimate
needs a fresh independently written set.** [REVIEW.md](../../REVIEW.md) section 3 asks
reviewers for exactly that.

## Development set

The development set is used for tuning and regression testing (CI fails if it regresses).
Its scores are expected to be near 100% and say little about real accuracy.
