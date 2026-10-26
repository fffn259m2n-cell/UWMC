"""Meaning-change checks shared by teach-back and the fidelity evaluator.

Each check compares a free-text restatement (a patient's explanation, or a rewritten
instruction) with the documented original and reports a *change* the original does not
support: a different time of day, food rule, period for a limit, an added stop
condition, an emergency sign paired with something other than 911, and so on.

These are rule-based and deliberately conservative. They catch common, specific
patterns; they cannot understand language in general, and an absence of findings is
never evidence that a text is correct.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import text


@dataclass(frozen=True)
class Change:
    check: str
    message: str
    fact_id: str | None = None


def _t(s: str) -> str:
    return text._words_to_digits(text.normalize(s))


def _live(t: str, m: re.Match) -> bool:
    """The match is not negated ("I would not wait")."""
    return not text.is_negated(t, m.start())


# ---------------------------------------------------------------- time of day
TIME_OF_DAY = {
    "morning": r"\b(morning|mornings|breakfast|a\.?m\.?|manana|desayuno)\b",
    "afternoon": r"\b(afternoon|lunch|noon|midday|tarde)\b",
    "evening": r"\b(night|nights|bedtime|evening|evenings|dinner|supper|p\.?m\.?|noche|cena|before bed|go to bed)\b",
}
ONLY_ONE_TIME = r"\b(morning|night|evening|bedtime) only\b|\bonly (in the |at )?(morning|night|evening|bedtime)\b"


def times_of_day(s: str) -> set[str]:
    """Times of day mentioned without negation ("not at night" does not count)."""
    t = _t(s)
    return {k for k, p in TIME_OF_DAY.items() if any(_live(t, m) for m in re.finditer(p, t))}


# ---------------------------------------------------------------- food
WITH_FOOD = r"\bwith (food|a meal|meals|breakfast|dinner)\b|\bcon (comida|alimentos)\b"
FOOD_CHANGED = (r"\bempty stomach\b|\bwithout (food|eating|a meal)\b|\bfood (doesn'?t|does not|don'?t) matter\b"
                r"|\b(doesn'?t|does not) matter (if|whether) (i|you) eat\b|\bbefore (food|meals?|eating|i eat|you eat)\b"
                r"|\bno food\b|\bsin comida\b|\ben ayunas\b")

# ---------------------------------------------------------------- stopping, pausing, extra doses
STOP_CONDITION = (
    r"\b(until|till|once|when|whenever|if|unless) (i|you|my \w+|your \w+|the \w+) (feel|feels|am|are|is|get|gets|seem|seems)"
    r"( \w+)? (better|fine|normal|good|ok|okay|well|back to normal|gone|over|slow|dizzy)\b"
    r"|\bthen (i'?m|i am|you'?re|you are) (done|finished)\b|\bi'?m (done|finished)\b"
    r"|\b(bottle|pills?|prescription|medicine) (runs?|run) out\b|\bwhen (it|they) runs? out\b"
    r"|\btake a break\b|\b(skip|miss|hold|stop|pause) (it |them |the dose |a dose |doses )?(on|during|over) (weekends?|days|the weekend|holidays|trips?)\b"
    r"|\b(hold|skip|stop|pause|miss) (it|them|taking it|the dose|a dose)? ?(if|when|whenever)\b|\b(i|you) (stop|hold|skip) (it )?if\b"
    r"|\bonly (when|if) (my|i|you|your)\b|\bsave (a few|some|the rest|them|the extras?|the leftovers?|leftovers?)\b|\bfor next time\b|\b(stop|hold|skip|pause) (it|them|the \w+|my \w+) (for|until)\b|\bif my (blood pressure|bp|heart rate|pulse)\b|\bin case (i|you) get sick\b"
    r"|\bdon'?t worry (if|about) (you |i )?(skip|miss|forget)\w*\b|\b(it'?s|is) (ok|okay|fine) to (skip|miss)\b"
    r"|\bdeje de tomar\b|\bpuede dejar\b|\bcuando se sienta mejor\b"
)
DOUBLE_UP = (r"\bdouble (up|the dose|my dose|it)\b|\bmiss\w* (a|one|the) dose\b[^.]{0,40}\b(take|have) (2|two|both|double|an extra|extra)\b"
             r"|\btake (another|an extra|extra|1 more|one more|2 more|more)\b(?! than)|\bplus extra\b|\bextra (at|in the|if|when|on)\b"
             r"|\b(1|one) more (pill|tablet|dose)\b|\btake (2|two) the next time\b")

# ---------------------------------------------------------------- warnings: normalising and delaying
NORMALISING = (r"\b(no|not a) big deal\b|\bnothing serious\b|\b(a )?good sign\b|\ba good thing\b|\bthat'?s good\b|\bbreaking up\b"
               r"|\bmeans (it'?s|she'?s|he'?s|i'?m|you'?re) (healing|better|eating|working|getting better)\b"
               r"|\b(is|are|'s|'re|were|was) (just |totally |pretty |completely |perfectly )?(normal|expected|common|nothing|fine|harmless|ok|okay)\b"
               r"|\bjust (from|because of|a side effect)\b|\bis (a )?(normal|expected) (side effect|part)\b"
               r"|\b(i|you) (don'?t|do not|won'?t|wouldn'?t) (need to |have to )?(worry|call|bother|bring)\b|\bno need to (call|worry|bring|go)\b"
               r"|\bnothing to worry about\b|\bso (i|you) (just )?(wait|ignore|leave)\b|\b(i|you) just (wait|ignore|rest|sleep|lie down|drink less)\b"
               r"|\bson normales\b|\bes normal\b")
DELAY = (r"\b(next|upcoming) (appointment|visit|checkup|check-up|clinic visit)\b|\bmention it\b|\btell (them|my doctor|the doctor) (at|when|next)\b"
         r"|\buntil (monday|tomorrow|the morning|morning|the weekend|next week|later)\b|\b(tomorrow|in the morning|next day|later on|monday)\b"
         r"|\bif it'?s still (there|happening|going)\b|\bstill there when\b|\bif it (keeps|continues|lasts|doesn'?t go away)\b"
         r"|\b(only )?if it lasts\b|\blasts? (more|longer) than\b|\b(do|does) not go away after\b|\bafter a (few|couple of) (hours|minutes|days)\b"
         r"|\b(take|have) a nap\b|\bnap\b|\blie down\b|\bsleep (it off|on it)\b|\bsee (if|how)\b|\bwait\b(?! for (the )?(ambulance|paramedics|help|911|emts?))|\bbefore calling\b|\bfor an hour\b|\bkeep (pressing|holding)\b[^.]{0,30}\b(hour|before)\b")

# ---------------------------------------------------------------- emergency: other actions in place of 911
OTHER_ACTION = (r"\b(call|ring|phone|text|message) (my|the|your|a|our)\b(?! ?911)|\b(go|drive|head|get|take (me|myself)) to\b|\bdrive (myself|me)\b"
                r"|\burgent care\b|\b(clinic|cardiologist|primary care|doctor|nurse line|pharmacy)\b|\b(take|took|use|chew) (an? |my |some |the |a few )?(aspirin|tylenol|nitro\w*|pills?|medicine|\w+ pill|extra|another|ibuprofen|advil)\b"
                r"|\b(come get|pick me up|drive me|take me)\b|\b(lie|lay) down\b|\bnap\b|\brest\b|\bwait\b")
ALTERNATIVE_TO_911 = (r"\b911 or (have|ask|get|go|call (the|your|my) (clinic|doctor))\b|\b(clinic|doctor|cardiologist|someone|family member)\b[^.]{0,30}\bor (call )?911\b"
                      r"|\bor (have|ask|get) (a |an? )?(family member|friend|someone|somebody|neighbor)\b[^.]{0,20}\b(drive|take)\b")

# ---------------------------------------------------------------- limits
UNLIMITED = (r"\b(plenty of|as much as|as much \w+ as|as many as|no limit|unlimited|all (i|you) want|lots of|a lot of)\b"
             r"|\bmore (if|when) (you'?re|you are|i'?m|i am) thirsty\b|\bmore\b[^.]{0,20}\b(is|are) (fine|ok|okay|allowed)\b"
             r"|\b(is|are) (ok|okay|fine) as long as\b|\bno max\w*\b|\bwhenever (i|you) (want|like|need)\b|\btake it whenever\b|\bmore on (weekends?|holidays|special)\b|\bon weekdays\b|\bexcept (on )?weekends\b"
             r"|\bsave (them|it|my \w+)? ?up\b|\bcatch up\b|\b(don'?t|doesn'?t|do not|does not|won'?t) count\b")
GAIN, LOSS = r"\b(gain|gains|gained|goes up|go up|went up|increase\w*|up by|heavier)\b", r"\b(lose|loses|lost|loss|goes down|go down|went down|drop\w*|decrease\w*|lighter)\b"
PERIOD = (r"(?:in|per|within|a|an|each|every|over|en|al|por)\s+(?:(1|2|3|4|5|6|7|a|an|one|un|una)\s+)?"
          r"(day|week|month|hour|24 hours|meal|dose|serving|sitting|time|dia|semana)s?\b")
NON_DAILY = (r"\bonce a week\b|\bevery other (morning|night|evening)\b|\bevery (other day|week|few days|2 days|couple (of )?days)\b|\bweekly\b|\b(a few|couple of|2|3) times a week\b"
             r"|\bnow and then\b|\bonly (take|use|weigh|need|do|get)\b[^.]{0,30}\b(when|if|on days)\b|\b(just|only) for when\b|\b(una|1) vez (por|a la) semana\b|\bcada semana\b|\bsemanal\w*\b|\bwhenever (i|you) remember\b|\bonly (need to|have to)\b[^.]{0,30}\b(when|if)\b|\bonly (on days|on the days|when|if)\b|\bon (the )?days (i|you|when)\b|\bsome days\b")
DAILY = r"\bevery (day|morning|night|evening)\b|\bdaily\b|\beach (day|morning)\b|\b(once|twice|\d times) (a|per|each) day\b"
AS_NEEDED = r"\bas needed\b|\bif (you|i) need\b|\bwhen needed\b|\bif needed\b"
COMBINED = r"\bboth\b[^.]{0,25}\bin the (morning|evening)\b|\bnone (at night|at bedtime|in the morning|in the evening)\b|\b(both|all)\b[^.]{0,40}\b(together|at once|at the same time)\b|\btogether at (breakfast|dinner|night|bedtime)\b"
RESTRICT_FLUIDS = r"\b(as little as possible|drink less|limit (how much|fluids|drinking|what)|cut back on (fluids|drinking|water)|not too much (water|fluid))\b"
SKIP_FOLLOW_UP = (r"\bwhenever\b|\bafter the holidays\b|\bwhen i get (around|a chance)\b|\bsometime\b|\bsomeday\b|\bno rush\b|\beventually\b"
                  r"|\b(isn'?t|is not|aren'?t) (really )?(necessary|needed|important)\b|\byearly\b|\bannual\b|\bphysical\b|\bin the (spring|summer|fall|autumn|winter)\b|\bnext year\b|\bonly\b[^.]{0,30}\b(if|when)\b|\balready done\b|\bno more (needed|necessary)\b|\bskip\b|\bno need\b|\b(don'?t|do not|won'?t) (really )?need\b"
                  r"|\bnot (necessary|needed|important)\b|\bif (i'?m|i am) not (getting )?better\b|\bcan skip\b|\b(already|just) (did|had|got)\b")


def limit_periods(s: str) -> set[tuple[str, float, str]]:
    """(unit, value, period) for limits such as "2,000 mg a day" or "3,000 mg in 24 hours"."""
    t = _t(s)
    out = set()
    for n in text.numbers(s):
        if n.unit not in {"mg", "liters", "cups", "pounds", "drinks"}:
            continue
        m = re.match(r"^\s*(?:mg|milligrams?|pounds?|lbs?|liters?|litres?|cups?|drinks?)?\s*(?:\([^)]*\)\s*)?(?:of [a-z ]{0,20}?)?\s*(?:\([^)]*\)\s*)?(?:or more\s+)?" + PERIOD, t[n.span[1]:])
        if m:
            count, period = m.group(1), m.group(2)
            period = {"dia": "day", "semana": "week", "time": "dose"}.get(period, period)
            if period == "24 hours":
                period, count = "day", "1"
            k = 1 if count in (None, "a", "an", "1", "one", "un", "una") else int(count)
            out.add((n.unit, n.value, f"{k} {period}"))
    return out


def _sentences(t: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", t) if s.strip()]


def _clauses(sentence: str) -> list[str]:
    parts = re.split(r",(?=\s*(?:and |so |or )?(?:for|if|when|i|i'?d|i'?ll|i will|i would|my|we)\b)|\bbut\b|\bthen\b|\bwhile\b", sentence)
    return [c for c in parts if c.strip()]


def _has_911(s: str) -> bool:
    return any(not neg for neg in text.phrase_states(s, "911")) or bool(re.search(r"\bambulance\b", s))


def emergency_sign_phrases(item) -> list[str]:
    out = []
    for f in item.facts:
        if f.emergency:
            for g in f.concepts:
                if not any(p in ("911", "ambulance", "emergency") for p in g):
                    out += g
    return out


def compare(item, candidate: str, *, patient: bool) -> list[Change]:
    """Meaning changes between ``item.original`` and ``candidate``.

    ``patient=True`` (teach-back) skips checks that would fire on a correct but
    incomplete explanation, such as a limit restated without "no more than".
    """
    src, cand = _t(item.original), _t(candidate)
    out: list[Change] = []

    def add(check, msg, fact_id=None):
        if not any(c.check == check for c in out):
            out.append(Change(check, msg, fact_id))

    def live(pattern, s=cand):
        return any(_live(s, m) for m in re.finditer(pattern, s))

    is_med = item.kind == "medication"
    src_nums = text.numbers(item.original)
    cand_nums = text.numbers(candidate)

    # Time of day
    src_tod = times_of_day(item.original)
    if src_tod:
        extra = times_of_day(candidate) - src_tod
        if extra:
            add("time_of_day_changed", f"The instruction says {' and '.join(sorted(src_tod))}; this mentions {' and '.join(sorted(extra))}.")
    if any(n.unit == "per_day" and n.value >= 2 for n in src_nums) and re.search(
            ONLY_ONE_TIME + r"|\bthat'?s it for the day\b|\b(only|just) once\b", cand):
        add("frequency_changed", "The instruction gives more than one dose a day; this mentions only one time of day.")
    if re.search(r"\bonce or twice\b|\b1 or 2 times\b", cand) and not re.search(r"\bonce or twice\b|\b1 or 2 times\b", src):
        add("frequency_changed", "“Once or twice” leaves the number of doses open; the instruction gives one number.")
    if re.search(DAILY, src) and live(NON_DAILY):
        add("frequency_changed", "The instruction says every day; this describes something less often.")

    # Food
    if re.search(WITH_FOOD, src) and re.search(FOOD_CHANGED, cand):
        add("food_changed", "The instruction says to take it with food; this says otherwise.")

    # Stopping, pausing and extra doses
    if is_med:
        for m in ([] if re.search(AS_NEEDED, src) else re.finditer(STOP_CONDITION, cand)):
            before = cand[max(0, m.start() - 12):m.start()]
            if re.search(r"\beven(?: (if|when|though))?\s*$", before) or text.is_negated(cand, m.start()) \
                    or re.match(r"[^.]{0,25}\b(my|your|the) (cardiologist|doctor|care team|provider) (tells|says|asks)", cand[m.end() - 8:]):
                continue
            if m.group(0) in src:
                continue
            add("stop_condition_added", f"“{m.group(0)}” adds a reason or time to stop, skip or pause that the instruction does not give.")
            break
        no_double = re.search(r"\b(don'?t|do not|never|not|won'?t) (take|have) (double|2|two|extra|another|both|more)\b", cand)
        if live(DOUBLE_UP) and not no_double and not re.search(DOUBLE_UP, src):
            add("dose_added", "This mentions taking more or an extra dose; the instruction does not say that.")
        tabs_src = {n.value for n in src_nums if n.unit == "tablets"} | {1.0}
        names = "|".join(re.escape(text.normalize(n)) for n in item.drug_names) or r"(?!)"
        counts = [(float(m.group(1)), m.start()) for m in re.finditer(
            rf"\b(\d{{1,2}}) (?:of (?:the|my|your) )?(?:\d+(?:\.\d+)? ?mg )?(?:{names})\b", cand)]
        counts += [(n.value, n.span[0]) for n in cand_nums if n.unit == "tablets"]
        counts += [(float(m.group(1)), m.start()) for m in re.finditer(
            r"\b(\d{1,2}) of the (?:\d+s\b|[a-z ]{0,25}?\b(?:pills|tablets|capsules)\b)", cand)]
        for value, pos in counts:
            if value > max(tabs_src) and re.match(r"\d+\s*(?:tablets?|pills?|tabs?|capsules?)?\s*(?:total\s+)?(?:in|per) (?:1 |a |one )?(?:day|24)", cand[pos:pos + 60]):
                continue   # a daily total ("no more than 9 pills in a day"), not a per-dose count
            if value not in tabs_src:
                add("tablet_count_changed", f"“{value:g}” tablets or pills per dose does not match the instruction.")
        src_freq = {n.value for n in src_nums if n.unit == "per_day"}
        m = re.search(rf"\b(\d) (?:{names})s? (?:a|per|each) day\b", cand)
        if m and src_freq and float(m.group(1)) not in {f * t for f in src_freq for t in tabs_src}:
            add("frequency_changed", f"“{m.group(0)}” does not match how often the instruction says to take it.")
        if live(COMBINED) and not re.search(COMBINED, src):
            add("doses_combined", "This describes taking doses together; the instruction spaces them out.")
        pairs = re.findall(r"(\d+(?:\.\d+)?)\s*(?:mg)?\s*/\s*(\d+(?:\.\d+)?)", src)
        for a, b in pairs:
            if a != b and re.search(rf"\b{re.escape(b)}\s*(?:mg)?\s*/\s*{re.escape(a)}\b", cand):
                add("strength_swapped", f"The two strengths are in the opposite order ({b}/{a} instead of {a}/{b}).")
    elif live(DOUBLE_UP) and not re.search(DOUBLE_UP, src) and re.search(r"\b(pill|water pill|dose|metoprolol|furosemide|lasix|medicine|aspirin|antibiotics?)\b", cand):
        add("dose_added", "This mentions taking an extra or additional medicine; the instruction does not say that.")

    # Warnings and calls: normalising or delaying something the instruction says to act on
    acts = item.kind in ("warning",) or bool(re.search(r"\bcall\b", src))
    if acts and item.kind not in ("appointment", "test"):
        for m in re.finditer(NORMALISING, cand):
            if not text.is_negated(cand, m.start()) and m.group(0) not in src:
                add("warning_normalised", f"“{m.group(0)}”: the instruction treats this as a reason to call, not as normal.")
                break
        for m in re.finditer(DELAY, cand):
            sentence_before = cand[:m.start()].rsplit(".", 1)[-1]
            if re.search(r"\b(don'?t|do not|never|without|no) wait", sentence_before):
                continue
            if not text.is_negated(cand, m.start(), window=3) and m.group(0) not in src:
                add("action_delayed", f"“{m.group(0)}”: the instruction says to call when this happens, without waiting.")
                break
    if not is_med:
        m = re.search(r"\b(i'?ll|i will|i'?d|i would|going to|i can|i could|i) (just )?(stop|skip|hold) (it|them|taking \w+|my [a-z ]{0,20}?(pills|meds|medicines?|medication|antibiotics?))\b", cand)
        if m and not text.is_negated(cand, m.start()):
            add("stop_condition_added", f"“{m.group(0)}”: your instructions do not say to stop a medicine.")
    if item.kind in ("appointment", "test"):
        for m in re.finditer(SKIP_FOLLOW_UP, cand):
            if not text.is_negated(cand, m.start()) or re.match(r"(no need|don'?t|do not|won'?t)", m.group(0)):
                if not re.search(r"\b(don'?t|do not|never|won'?t|shouldn'?t) (skip|miss)\b", cand):
                    add("instruction_dropped", f"“{m.group(0)}”: the instruction gives this visit or test without conditions.")
                    break
    if re.search(r"\bplenty\b|\blots of (fluids|water)\b|\bmore fluids\b", src) and live(RESTRICT_FLUIDS):
        add("limit_reversed", "The instruction says to drink plenty; this says to drink less.")
    if re.search(r"\bpackage directions\b|\bas directed\b", src) and live(UNLIMITED):
        add("limit_loosened", "The instruction says to follow the package directions; this describes no limit.")

    # Emergency signs paired with something other than 911
    signs = emergency_sign_phrases(item)
    if signs:
        for sent in _sentences(cand):
            parts = _clauses(sent) if _has_911(sent) else [sent]
            for part in parts:
                if _has_911(part):
                    continue
                sign = next((p for p in signs if text.find_phrase(part, p)), None)
                if sign and re.search(OTHER_ACTION, part):
                    add("emergency_sign_not_with_911", f"“{sign}” is paired with another action; the instruction says to call 911.")
        if re.search(ALTERNATIVE_TO_911, cand) and not re.search(ALTERNATIVE_TO_911, src):
            add("alternative_to_911", "This offers another option alongside 911; the instruction says to call 911.")

    # Limits and thresholds
    src_dirs = text.directions(item.original)
    if any("upper" in d for d in src_dirs.values()) and live(UNLIMITED) and not re.search(UNLIMITED, src):
        add("limit_loosened", "The instruction sets a maximum; this describes it as open-ended or with exceptions.")
    if not patient:
        cand_dirs = text.directions(candidate)
        for (unit, value), d in src_dirs.items():
            hits = [n for n in cand_nums if n.unit == unit and n.value == value]
            # "2 liters, which is about 8 cups": a conversion of a limit already stated
            if all(re.search(r"\b(about|approximately|around|roughly)\s*$", cand[:n.span[0]]) for n in hits):
                continue
            if "upper" in d and hits and not cand_dirs.get((unit, value)):
                add("limit_softened", f"“{value:g} {unit}” is a maximum in the instruction but not stated as a limit here.")
    if re.search(GAIN, src) and re.search(LOSS, cand) and not re.search(LOSS, src):
        add("direction_changed", "The instruction is about weight going up; this describes it going down.")
    sp, cp = limit_periods(item.original), limit_periods(candidate)
    src_units = {(u, v) for u, v, _ in sp}
    changed = {(u, v, p) for u, v, p in cp if (u, v) in src_units and (u, v, p) not in sp}
    if changed:
        u, v, p = sorted(changed)[0]
        add("period_changed", f"“{v:g} {u}” is given per {p}; the instruction gives a different period.")
    if re.search(r"\bor (more than|if)\b", src) and re.search(r"\band (more than)\b", cand) and not re.search(r"\bor (more than|if)\b", cand):
        add("or_changed_to_and", "The instruction says “or” (either one is enough); this says “and”.")

    # A "do not ... unless" instruction with a different or extra exception
    if not patient:
        generic = {"your", "you", "tells", "tell", "told", "says", "said", "asks", "asked", "that", "this", "with", "them"}
        allowed = {w for tail in re.findall(r"\b(?:unless|except|or if)\b([^.]*)", src) for w in re.findall(r"[a-z]{4,}", tail)}
        for m in re.finditer(r"\b(?:do not|don'?t|never)\b[^.]*?\b(unless|except|or if)\b([^.]*)", cand):
            new = [w for w in re.findall(r"[a-z]{4,}", m.group(2)) if w not in allowed and w not in generic]
            if new:
                add("exception_added", f"“{m.group(1)}{m.group(2)}” adds an exception the instruction does not give.")
                break
        if re.search(r"\bmore\b[^.]{0,60}\bthan (the package|the label|directed|recommended|it says|the box)\b", cand) \
                and re.search(r"\b(do not|don'?t|never) (take|use)\b", src) and not re.search(r"\bthan the package\b", src):
            add("prohibition_weakened", "The instruction says not to take this at all; this only limits the amount.")
        # Spanish: "Puede tomar ibuprofeno" where the original says not to take it.
        for f in item.facts:
            if f.action and f.action.objects:
                stems = "|".join(re.escape(o.lower()[:6]) for o in f.action.objects)
                if re.search(rf"(?<!no )\b(puede|pueden|podra|podria) (tomar|usar)\b[^.]{{0,40}}\b({stems})", cand) \
                        or re.search(rf"\b({stems})\w*\b[^.]{{0,50}}\b(esta|estan) bien\b", cand):
                    add("negation_possibly_lost", "The text appears to allow a medicine the original says not to take (“puede tomar…”).", f.id)
    return out
