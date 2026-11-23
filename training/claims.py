"""Rule-based check for qualitative case study claims that the project data does not support.

The app's number filter catches invented numbers only. These rules flag the claims it misses: all touch
targets meeting 44 px when they do not, smooth or successful tasks when the tests say otherwise, confirmed or
validated findings without confirmed interview hypotheses, measured outcomes or iterations that never happened,
quoting the model-written persona quote, and statements about research, tests, team or timeline that the fact
sheet lists as missing. Each flag is (field, rule, sentence).
"""

from __future__ import annotations

import re
from typing import Any

NEGATION = re.compile(r"\b(nie|ani|żaden|żadna|żadne|not|no|none|never|without|n't)\b|n't\b", re.I)
PLAN = re.compile(r"\b(kolejn\w*|następn\w*|zaplanuj\w*|planujemy|powtórzymy|przeprowadzimy|sprawdzimy|zbadamy|porozmawia\w*|warto|trzeba|musi\w*|powinn\w*|next|will|plan\w*|need to|should|we'll|ideally)\b", re.I)

RULES = {
    "targets_all": re.compile(r"(wszystkie|każdy|każdego|wszystkich)\b[^.]*\b(cel\w* dotykow\w*|44 ?px)|(cel\w* dotykow\w*|44 ?px)[^.]*\b(wszystkie|każdy|spełnia\w*)\b|\b(all|every)\b[^.]*\b(touch targets?|44 ?px)|(touch targets?|44 ?px)[^.]*\b(all|every|meet|comply)\b", re.I),
    "smooth_tasks": re.compile(r"\b(pomyślnie|z powodzeniem|bez (większych )?(problemów|trudności|trudu)|bez trudu|łatwo|łatwość|intuicyjn\w*|sprawnie|płynnie|successfully|easily|with ease|without (any )?(problems?|difficult\w*|issues?|trouble)|intuitive\w*|seamless\w*|smooth\w*)\b", re.I),
    "validated": re.compile(r"\b(potwierdzi\w*|potwierdzon\w*|potwierdza\w*|zwalidowa\w*|walidacj\w+ potwierdzi\w*|zweryfikowa\w*|udowodni\w*|dowodz\w*|confirm\w*|validat\w*|verif\w*|prov(ed|es|en))\b", re.I),
    "outcome": re.compile(r"\b(wzrósł|wzrosła|wzrosło|wzrosły|spadł|spadła|spadło|zwiększył\w*|zmniejszył\w*|poprawił\w*|poprawiliśmy|skrócił\w*|skróciliśmy|ulepszyliśmy|konwersj\w*|przychod\w*|przychód|zadowoleni\w*|satysfakcj\w*|increased|decreased|reduced|improved|boosted|conversion|revenue|retention rate|satisf\w+|NPS|ROI)\b", re.I),
    "well_received": re.compile(r"\b(spodobał\w*|pokochali|chwalili|entuzjastycz\w*|pozytywn\w+ (odbiór|reakcj\w*|opini\w*)|loved|liked it|well received|positive (feedback|reception|response)|enthusias\w*|delighted)\b", re.I),
    "team_timeline": re.compile(r"\b(zesp[oó]ł\w*|zespo\w+|team\w*|\d+ (tygodni|tydzień|tygodnie|miesi\w+|dni|weeks?|months?|days?)|sprint\w*|stakeholder\w*|interesariusz\w*)\b", re.I),
}
INTERVIEW = re.compile(r"\b(wywiad\w*|rozmow\w*|rozmawial\w*|interview\w*|conversation\w*|spoke with|talked to)\b", re.I)
TESTS = re.compile(r"\b(test\w*|uczestni\w*|participant\w*|badani\w* użyteczn\w*|usability)\b", re.I)


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s]


QUOTED = re.compile(r"„[^”]*”|“[^”]*”|\"[^\"]*\"")


def project_terms(context: dict[str, Any]) -> list[str]:
    """Names and phrases taken from the project itself, which are not claims by the writer."""
    persona = context.get("persona") or {}
    problem = context.get("problem") or {}
    empathy = context.get("empathy") or {}
    board = context.get("board") or {}
    flow = context.get("flow") or {}
    terms = [
        context["project"].get("seed", ""), context["project"].get("name", ""),
        persona.get("name", ""), persona.get("role", ""), persona.get("focus", ""),
        problem.get("title", ""), empathy.get("hmw_chosen") or "",
        *(t.get("name", "") for t in board.get("themes") or []),
        *(f.get("title", "") for f in context.get("features") or []),
        *(s.get("name", "") for s in flow.get("screens") or []),
    ]
    return sorted({t.strip().rstrip("?") for t in terms if t and len(t.strip()) > 2}, key=len, reverse=True)


def strip_project_text(sentence: str, terms: list[str]) -> str:
    text = QUOTED.sub(" ", sentence)
    for term in terms:
        text = re.sub(re.escape(term), " ", text, flags=re.I)
    return text


def unsupported_claims(fields: dict[str, str], context: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Flag sentences whose qualitative claims the project context does not support."""
    terms = project_terms(context)
    audit = context.get("audit") or {}
    targets = audit.get("targets") or {}
    all_targets = bool(targets.get("total")) and targets.get("aaa", 0) == targets["total"]
    tests = context.get("tests") or {}
    tasks = [t for t in tests.get("tasks", []) if t.get("attempts")]
    has_tests = bool(tests.get("participants")) and bool(tasks)
    all_succeeded = has_tests and all(t["successes"] / t["attempts"] >= 0.8 for t in tasks) and not tests.get("issues")
    validation = context.get("validation") or {}
    interviews = validation.get("interviews") or []
    confirmed = any(h.get("status") == "confirmed" for h in validation.get("hypotheses") or [])
    board = context.get("board") or {}
    spoken = any(n.get("source") in ("interview", "note") for n in board.get("notes") or [])
    persona = context.get("persona") or {}
    model_quote = persona.get("quote", "") if persona and not (persona.get("profile") or {}).get("quote_source") else ""

    flags = []
    for field, text in fields.items():
        for original in sentences(text or ""):
            sentence = strip_project_text(original, terms)
            negated = bool(NEGATION.search(sentence))
            planned = bool(PLAN.search(sentence))
            if RULES["targets_all"].search(sentence) and not all_targets and not negated and not planned:
                flags.append((field, "targets_all", original))
            if RULES["smooth_tasks"].search(sentence) and not all_succeeded and not negated:
                flags.append((field, "smooth_tasks", original))
            if RULES["validated"].search(sentence) and not negated and not planned and not (confirmed and INTERVIEW.search(sentence)):
                flags.append((field, "validated", original))
            if RULES["outcome"].search(sentence) and not negated and not planned:
                flags.append((field, "outcome", original))
            if RULES["well_received"].search(sentence) and not negated:
                flags.append((field, "well_received", original))
            if RULES["team_timeline"].search(sentence):
                flags.append((field, "team_timeline", original))
            if not interviews and not spoken and INTERVIEW.search(sentence) and not planned and not negated:
                flags.append((field, "missing_interviews", original))
            if not has_tests and TESTS.search(sentence) and not planned:
                flags.append((field, "missing_tests", original))
            if model_quote and len(model_quote) > 20 and model_quote[:25].lower() in original.lower():
                flags.append((field, "model_quote", original))
    return flags
