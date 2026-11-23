"""Professional UX case study written only from the project's own data, with gaps left for the designer."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from ..models import CaseStudyDraft, Flow
from ..ollama_client import OllamaError
from .discover import LANGUAGE_NAMES
from .jobs import ProgressFn, WarnFn

GUIDE_NOTES = (
    "Studied 26 case studies of mobile and web apps from UX/UI designers' own portfolios (sources below).",
    "They run 1260-2210 words (median 1540) with about 33 images.",
    "21 of 26 open with an overview of role, timeline and tools; 25 show research, 25 a persona, 24 usability testing, 21 a reflection.",
    "Only 11 of 26 back findings with numbers, and those state a denominator: 5 of 7 users, 6 participants.",
)

GUIDE = (
    ("summary", "Overview: one-paragraph TL;DR with the problem, what was designed and the headline test result, plus role, timeline, team and tools.", "60-120"),
    ("context", "Problem and context: the problem statement, why it matters to the persona and the chosen How might we.", "80-150"),
    ("research", "Research: methods with their sample sizes (sources, interviews), what each revealed; numbers carry their denominator.", "120-250"),
    ("synthesis", "Synthesis: affinity themes with note counts, persona with a real quote, empathy map, journey pain points, HMW.", "150-300"),
    ("ideation", "Ideas and priorities: how the backlog was scored (MoSCoW, RICE) and which features made the cut.", "80-150"),
    ("design", "Design: the user flow, the path to the goal and the heuristic audit; visuals are screenshots of the flow.", "100-200"),
    ("testing", "Usability testing: tasks, participants, success as x of y, time on task against a prediction, issues with quotes.", "120-250"),
    ("outcomes", "Outcomes: only measured results, as before/after or x of y; business impact only when it was measured.", "60-150"),
    ("reflection", "Reflection and next steps: short headed lessons, compromises, what to test next.", "100-200"),
)

GUIDE_SOURCES = (
    "https://julieanaff.myportfolio.com/1",
    "https://moriyajaffe.myportfolio.com/fly-ux-case-study",
    "https://www.kellymartin.design/case-study-navigate",
    "https://lfilice.myportfolio.com/uxui-case-study",
    "https://hastiibhalodiya.framer.website/case-study-1",
    "https://gatherapp.framer.website/",
    "https://minernkoh.framer.website/projects/letterboxd",
    "https://leonalaidesigns.framer.website/case2-webreg",
    "https://cephasweror.framer.ai/miidle-casestudy",
    "https://colearn-casestudy.framer.website/",
    "https://ishams.webflow.io/case-studies/c-s-case-study",
    "https://samslate1.webflow.io/project/corenav",
    "https://felicias-portfolio-532362.webflow.io/ux-projects/poolup-app",
    "https://josephpanux.webflow.io/case-study-spotify",
    "https://brianfoong.webflow.io/case-study/cloudcast",
    "https://daniheryanto.webflow.io/portfolio-edcuration",
    "https://devikakool.webflow.io/project/app-store-case-study",
    "https://paulinabryla.webflow.io/ui/designing-an-intuitive-travel-app-for-every-generation",
    "https://guspaludeti.webflow.io/starbucks-case-study",
    "https://jacquelai-portfolio-befd09.webflow.io/project/eatigo-redesign",
    "https://jacquelai-portfolio-befd09.webflow.io/project/travel-planning-app",
    "https://jeurysantos.webflow.io/pick-case-study",
    "https://elmirarehnert.webflow.io/webdesign-case-study",
    "https://sreeja-ux-ui-portfolio.webflow.io/projects/urban-farming-app",
    "https://portfolio-814c89.webflow.io/revo-case-study",
    "https://leander-designs.webflow.io/climate-case-study",
)

TEXT = {
    "pl": {
        "title": "Case study",
        "gap": "do uzupełnienia",
        "sections": {
            "summary": "Podsumowanie",
            "context": "Problem i kontekst",
            "research": "Badania",
            "synthesis": "Synteza",
            "ideation": "Pomysły i priorytety",
            "design": "Projekt rozwiązania",
            "testing": "Testy użyteczności",
            "outcomes": "Wyniki",
            "reflection": "Wnioski i kolejne kroki",
            "sources": "Źródła danych",
        },
        "meta": {"role": "Rola", "timeline": "Czas trwania", "team": "Zespół", "tools": "Narzędzia"},
        "tools": "PrismaFlow (Double Diamond), lokalny model językowy",
        "facts": "Fakty z projektu",
        "problem": "Problem",
        "quote": "Cytat",
        "hmw": "Jak moglibyśmy",
        "map": "Mapa Discover: {nodes} węzłów ({kinds}); oznaczone gwiazdką: {starred}",
        "evidence": "Zebrane sygnały z sieci: {total} ({sources})",
        "interviews": "Wywiady walidacyjne: {count}; hipotezy potwierdzone {confirmed}, obalone {rejected}, otwarte {open}",
        "board": "Tablica podobieństw: notatki {notes} ({sources}), tematy {themes}",
        "theme": "{name} (notatki: {count})",
        "persona": "Persona",
        "quote_real": "cytat z badań",
        "quote_model": "cytat napisany przez model",
        "empathy": "Mapa empatii: {grounded} z {total} elementów ma źródło w notatkach, wywiadach lub testach",
        "pain": "Najtrudniejszy moment ścieżki",
        "backlog": "Backlog: {counts}",
        "rice": "{title} — RICE {score} (R {reach} · I {impact} · C {confidence}% · E {effort})",
        "flow": "Przepływ: {screens} ekrany, {transitions} przejścia",
        "path": "Droga do celu: {path} ({steps} kroki)",
        "klm": "Przewidywany czas do celu (KLM): {seconds} s",
        "targets": "Cele dotykowe ≥ 44 px (WCAG 2.5.5 AAA): {aaa} z {total}; mniejszych: {below}",
        "dead": "Ślepe zaułki: {screens}",
        "hick": "Przeciążenie wyborem (Hick): {screens}",
        "participants": "Uczestnicy testów: {count}",
        "task": "Zadanie „{goal}”: sukces {successes} z {attempts} ({rate}%)",
        "time": "średni czas {seconds} s wobec {predicted} s przewidywanych przez KLM (×{ratio})",
        "time_only": "średni czas {seconds} s",
        "misclicks": "kliknięć bez efektu na osobę: {value}",
        "detours": "zboczenia ze ścieżki: {screens}",
        "issue": {
            "success": "Zadanie „{task}” ukończyło {successes} z {attempts} osób",
            "slow": "Zadanie „{task}” trwało {ratio}× dłużej niż przewiduje KLM",
            "detour": "W zadaniu „{task}” {count} os. zboczyło na ekranie {screen}",
            "misclick": "„{element}” na ekranie {screen} kliknięto bez efektu ({count}×)",
        },
        "issues": "Problemy wykryte w testach",
        "measured": "Zmierzone wyniki",
        "gaps": {
            "role": "Twoja rola w projekcie",
            "timeline": "czas trwania projektu",
            "team": "skład zespołu",
            "visuals": "zrzuty ekranów lub prototyp (prototyp-figma.svg z Handoff Pack)",
            "impact": "wpływ biznesowy i metryki po wdrożeniu — nie były mierzone",
            "iteration": "zmiany po testach i wynik kolejnej rundy testów",
            "personal": "osobista refleksja: co zrobiłabyś/zrobiłbyś inaczej",
            "research": "badania z ludźmi (wywiady, notatki z obserwacji)",
            "board": "pogrupowane notatki na tablicy",
            "empathy": "mapa empatii i ścieżka użytkownika",
            "features": "backlog funkcji z oceną RICE",
            "flow": "przepływ ekranów w Deliver",
            "tests": "wyniki testów użyteczności",
            "persona": "persona",
            "problem": "wybrany problem",
        },
        "priorities": {"must": "Must", "should": "Should", "could": "Could"},
        "kinds": {"niche": "nisza", "idea": "pomysł", "pain_point": "problem", "target_group": "grupa docelowa", "competitor": "konkurencja"},
        "footer": "Opis sekcji napisał lokalny model wyłącznie na podstawie faktów z projektu; zdania z liczbami spoza danych zostały usunięte. Liczby, cytaty i listy pochodzą bezpośrednio z PrismaFlow. Miejsca oznaczone „do uzupełnienia” wymagają Twoich danych.",
    },
    "en": {
        "title": "Case study",
        "gap": "to fill in",
        "sections": {
            "summary": "Overview",
            "context": "Problem and context",
            "research": "Research",
            "synthesis": "Synthesis",
            "ideation": "Ideas and priorities",
            "design": "Designing the solution",
            "testing": "Usability testing",
            "outcomes": "Outcomes",
            "reflection": "Lessons and next steps",
            "sources": "Data sources",
        },
        "meta": {"role": "Role", "timeline": "Timeline", "team": "Team", "tools": "Tools"},
        "tools": "PrismaFlow (Double Diamond), local language model",
        "facts": "Project facts",
        "problem": "Problem",
        "quote": "Quote",
        "hmw": "How might we",
        "map": "Discover map: {nodes} nodes ({kinds}); starred: {starred}",
        "evidence": "Web signals collected: {total} ({sources})",
        "interviews": "Validation interviews: {count}; hypotheses confirmed {confirmed}, rejected {rejected}, open {open}",
        "board": "Affinity board: {notes} notes ({sources}), {themes} themes",
        "theme": "{name} ({count} notes)",
        "persona": "Persona",
        "quote_real": "quote from research",
        "quote_model": "quote written by the model",
        "empathy": "Empathy map: {grounded} of {total} items trace back to notes, interviews or tests",
        "pain": "Hardest moment of the journey",
        "backlog": "Backlog: {counts}",
        "rice": "{title} — RICE {score} (R {reach} · I {impact} · C {confidence}% · E {effort})",
        "flow": "Flow: {screens} screens, {transitions} transitions",
        "path": "Path to the goal: {path} ({steps} steps)",
        "klm": "Predicted time to goal (KLM): {seconds} s",
        "targets": "Touch targets ≥ 44 px (WCAG 2.5.5 AAA): {aaa} of {total}; smaller: {below}",
        "dead": "Dead ends: {screens}",
        "hick": "Choice overload (Hick): {screens}",
        "participants": "Test participants: {count}",
        "task": "Task “{goal}”: success {successes} of {attempts} ({rate}%)",
        "time": "mean time {seconds} s against {predicted} s predicted by KLM (×{ratio})",
        "time_only": "mean time {seconds} s",
        "misclicks": "dead taps per person: {value}",
        "detours": "detours: {screens}",
        "issue": {
            "success": "Task “{task}” was completed by {successes} of {attempts} people",
            "slow": "Task “{task}” took {ratio}× longer than KLM predicts",
            "detour": "In task “{task}” {count} people detoured at {screen}",
            "misclick": "“{element}” on {screen} was tapped with no effect ({count}×)",
        },
        "issues": "Issues found in testing",
        "measured": "Measured results",
        "gaps": {
            "role": "your role in the project",
            "timeline": "project timeline",
            "team": "team",
            "visuals": "screenshots or the prototype (prototyp-figma.svg from the Handoff Pack)",
            "impact": "business impact and post-launch metrics — not measured",
            "iteration": "changes made after testing and the next test round",
            "personal": "personal reflection: what you would do differently",
            "research": "research with people (interviews, observation notes)",
            "board": "grouped notes on the board",
            "empathy": "empathy map and user journey",
            "features": "feature backlog with RICE scores",
            "flow": "screen flow in Deliver",
            "tests": "usability test results",
            "persona": "persona",
            "problem": "chosen problem",
        },
        "priorities": {"must": "Must", "should": "Should", "could": "Could"},
        "kinds": {"niche": "niche", "idea": "idea", "pain_point": "pain point", "target_group": "target group", "competitor": "competitor"},
        "footer": "The section narratives were written by a local model from the project facts only; sentences with numbers not found in the data were removed. Numbers, quotes and lists come straight from PrismaFlow. Places marked “to fill in” need your input.",
    },
}

SOURCE_NAMES = {
    "pl": {"autocomplete": "podpowiedzi wyszukiwarki", "community": "społeczności", "reddit": "Reddit", "trends": "Google Trends", "llm": "model", "interview": "wywiady", "note": "notatki", "evidence": "sieć", "test": "testy"},
    "en": {"autocomplete": "search suggestions", "community": "communities", "reddit": "Reddit", "trends": "Google Trends", "llm": "model", "interview": "interviews", "note": "notes", "evidence": "web", "test": "tests"},
}

SYSTEM = """You are a senior UX designer writing a portfolio case study from a project fact sheet.
Rules:
- Write in {language}, in the first person plural, in a calm professional tone.
- Use only facts from the fact sheet. Never invent numbers, percentages, participants, outcomes, business results,
  dates, team members or tools. If a fact is missing, do not mention it.
- Copy numbers exactly as written in the fact sheet. Do not compute new ones.
- Each field is plain prose without lists, headings or Markdown, at most 3 sentences.
- The fact lists and quotes are printed below your text, so do not repeat them: say what they mean for the persona
  and the design.
- Do not quote people or put words in their mouths. Quotes are what one person said, not research findings;
  a question someone asked is not an answer. A persona quote written by the model is not a user statement.
- Never say that something was well received, confirmed, validated, improved or successful unless a fact states it.
  Web signals are search suggestions and posts: they show what people look for, they do not confirm anything.
- Section order follows a professional case study: overview, problem, research, synthesis, ideas, design,
  usability testing, reflection. Reflection names lessons and next steps that follow from the test issues and gaps."""

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _words(language: str) -> dict[str, Any]:
    return TEXT["pl" if language == "pl" else "en"]


def _num(value: float | int, language: str) -> str:
    text = f"{value:g}" if isinstance(value, float) else str(value)
    return text.replace(".", ",") if language == "pl" else text


def _gap(words: dict[str, Any], key: str) -> str:
    return f"_[{words['gap']}: {words['gaps'][key]}]_"


def _counts(counter: Counter, names: dict[str, str], language: str) -> str:
    return ", ".join(f"{names.get(k, k)} {_num(v, language)}" for k, v in counter.most_common())


def case_study_facts(context: dict[str, Any]) -> dict[str, Any]:
    """Collect the facts each case study section may state, as Markdown lines, plus the gaps per section."""
    project = context["project"]
    language = project["language"]
    words = _words(language)
    names = SOURCE_NAMES["pl" if language == "pl" else "en"]
    facts: dict[str, list[str]] = {key: [] for key, _, _ in GUIDE}
    quotes: dict[str, list[str]] = {key: [] for key, _, _ in GUIDE}
    gaps: dict[str, list[str]] = {key: [] for key, _, _ in GUIDE}
    gaps["summary"] += ["role", "timeline", "team"]

    problem, persona = context.get("problem"), context.get("persona")
    empathy = context.get("empathy") or {}
    if problem:
        facts["context"].append(f"**{words['problem']}:** {problem['title']} — {problem['description']}")
        if problem.get("quote"):
            source = names.get(problem.get("quote_source") or "", problem.get("quote_source") or "")
            quotes["context"].append(f"„{problem['quote']}” _({source})_")
    else:
        gaps["context"].append("problem")
    if empathy.get("hmw_chosen"):
        facts["context"].append(f"**{words['hmw']}:** {empathy['hmw_chosen']}")

    nodes = context.get("nodes") or []
    if nodes:
        kinds = Counter(n["kind"] for n in nodes)
        starred = [n["label"] for n in nodes if n.get("starred") and not n.get("is_root")]
        facts["research"].append(
            words["map"].format(nodes=len(nodes), kinds=_counts(kinds, words["kinds"], language), starred=", ".join(starred[:8]) or "—")
        )
    evidence = context.get("evidence") or []
    if evidence:
        facts["research"].append(words["evidence"].format(total=len(evidence), sources=_counts(Counter(e["source"] for e in evidence), names, language)))
    validation = context.get("validation") or {}
    hypotheses = validation.get("hypotheses") or []
    interviews = validation.get("interviews") or []
    if interviews:
        status = Counter(h.get("status", "open") for h in hypotheses)
        facts["research"].append(
            words["interviews"].format(count=len(interviews), confirmed=status["confirmed"], rejected=status["rejected"], open=status["open"])
        )
        for h in hypotheses:
            for q in h.get("quotes", [])[:1]:
                quotes["research"].append(f"„{q['quote']}” _({q['person']})_")
    board = context.get("board") or {}
    notes = board.get("notes") or []
    human = [n for n in notes if n.get("source") in ("interview", "note", "test")]
    spoken = [n for n in notes if n.get("source") in ("interview", "note")]
    if not interviews and not human:
        gaps["research"].append("research")

    if notes:
        facts["synthesis"].append(
            words["board"].format(notes=len(notes), sources=_counts(Counter(n["source"] for n in notes), names, language), themes=len(board.get("themes") or []))
        )
        for theme in board.get("themes") or []:
            count = sum(1 for n in notes if n.get("theme") == theme["id"])
            line = words["theme"].format(name=theme["name"], count=count)
            facts["synthesis"].append(f"  - {line}" + (f": {theme['insight']}" if theme.get("insight") else ""))
        for note in spoken[:3]:
            quotes["research"].append(f"„{note['text']}” _({note.get('label') or names.get(note['source'], note['source'])})_")
    else:
        gaps["synthesis"].append("board")
    if persona:
        real = bool((persona.get("profile") or {}).get("quote_source"))
        facts["synthesis"].append(f"**{words['persona']}:** {persona['name']}, {persona['age']}, {persona['role']}; {persona.get('focus') or ''}".rstrip("; "))
        quotes["synthesis"].append(f"„{persona['quote']}” _({words['quote_real'] if real else words['quote_model']})_")
    else:
        gaps["synthesis"].append("persona")
    quadrants = [item for key in ("says", "thinks", "does", "feels") for item in empathy.get(key, [])]
    if quadrants:
        grounded = [item for item in quadrants if item.get("from")]
        facts["synthesis"].append(words["empathy"].format(grounded=len(grounded), total=len(quadrants)))
        journey = empathy.get("journey") or []
        if journey:
            worst = min(journey, key=lambda s: s.get("emotion", 0))
            facts["synthesis"].append(f"**{words['pain']}:** {worst['name']} ({worst['emotion']:+d}) — {worst.get('pain') or worst.get('action')}")
    else:
        gaps["synthesis"].append("empathy")

    features = context.get("features") or []
    if features:
        counts = Counter(f["priority"] for f in features)
        facts["ideation"].append(
            words["backlog"].format(counts=", ".join(f"{words['priorities'].get(k, k)} {v}" for k, v in sorted(counts.items(), key=lambda kv: list(words["priorities"]).index(kv[0]) if kv[0] in words["priorities"] else 9)))
        )
        ranked = sorted(features, key=lambda f: -(f.get("rice") or {}).get("score", 0))
        for feature in ranked[:5]:
            score = feature.get("rice") or {}
            facts["ideation"].append(
                "  - "
                + words["rice"].format(
                    title=feature["title"],
                    score=_num(float(score.get("score", 0)), language),
                    reach=_num(score.get("reach", 0), language),
                    impact=_num(float(score.get("impact", 1)), language),
                    confidence=round(100 * score.get("confidence", 0.5)),
                    effort=_num(float(score.get("effort", 2)), language),
                )
            )
    else:
        gaps["ideation"].append("features")

    flow = Flow.model_validate(context.get("flow") or {"screens": []})
    audit = context.get("audit") or {}
    if flow.screens:
        facts["design"].append(words["flow"].format(screens=audit.get("screens", len(flow.screens)), transitions=audit.get("transitions", 0)))
        steps = audit.get("steps") or {}
        if steps.get("value") is not None:
            facts["design"].append(words["path"].format(path=" → ".join(steps.get("path") or []), steps=steps["value"]))
        if audit.get("klm"):
            facts["design"].append(words["klm"].format(seconds=_num(float(audit["klm"]["seconds"]), language)))
        targets = audit.get("targets") or {}
        if targets.get("total"):
            facts["design"].append(words["targets"].format(aaa=targets.get("aaa", 0), total=targets["total"], below=targets["total"] - targets.get("aaa", 0)))
        if audit.get("dead_ends"):
            facts["design"].append(words["dead"].format(screens=", ".join(d["screen"] for d in audit["dead_ends"])))
        crowded = [h["screen"] for h in audit.get("hick", []) if h.get("warning")]
        if crowded:
            facts["design"].append(words["hick"].format(screens=", ".join(dict.fromkeys(crowded))))
    else:
        gaps["design"].append("flow")
    gaps["design"].append("visuals")

    tests = context.get("tests") or {}
    measured = []
    if tests.get("participants"):
        facts["testing"].append(words["participants"].format(count=tests["participants"]))
        for task in tests.get("tasks", []):
            if not task.get("attempts"):
                continue
            rate = round(100 * task["successes"] / task["attempts"])
            line = words["task"].format(goal=task["goal_name"], successes=task["successes"], attempts=task["attempts"], rate=rate)
            parts = [line]
            if task.get("seconds") is not None and task.get("predicted"):
                ratio = round(task["seconds"] / task["predicted"], 1)
                parts.append(words["time"].format(seconds=_num(float(task["seconds"]), language), predicted=_num(float(task["predicted"]), language), ratio=_num(ratio, language)))
            elif task.get("seconds") is not None:
                parts.append(words["time_only"].format(seconds=_num(float(task["seconds"]), language)))
            if task.get("misclicks"):
                parts.append(words["misclicks"].format(value=_num(float(task["misclicks"]), language)))
            if task.get("detours"):
                parts.append(words["detours"].format(screens=", ".join(f"{d['screen']} ({d['count']})" for d in task["detours"])))
            facts["testing"].append("; ".join(parts))
            measured.append("; ".join(parts[:2]))
            quotes["testing"] += [f"„{q['quote']}” _({q['participant']})_" for q in task.get("quotes", [])[:3]]
        issues = tests.get("issues") or []
        if issues:
            facts["testing"].append(f"**{words['issues']}:**")
            for issue in issues[:6]:
                template = words["issue"].get(issue["kind"])
                if template:
                    values = {k: (_num(v, language) if isinstance(v, float) else v) for k, v in issue.items()}
                    facts["testing"].append("  - " + template.format(**values))
    else:
        gaps["testing"].append("tests")
    if measured:
        facts["outcomes"].append(f"**{words['measured']}:**")
        facts["outcomes"] += [f"  - {line}" for line in measured]
    gaps["outcomes"] += ["impact", "iteration"]
    gaps["reflection"].append("personal")

    cited = context.get("cited") or []
    sources = list({e["url"]: e for e in cited if e.get("url")}.values())[:8]
    return {"facts": facts, "quotes": quotes, "gaps": gaps, "sources": sources}


def fact_sheet(context: dict[str, Any], collected: dict[str, Any]) -> str:
    """Plain-text fact sheet the model writes the narrative from."""
    project = context["project"]
    lines = [f'Project: "{project["name"]}" (niche: "{project["seed"]}")']
    for key, purpose, _ in GUIDE:
        lines.append(f"\n[{key}] {purpose}")
        lines += [re.sub(r"[*_]", "", line).strip() for line in collected["facts"][key]]
        lines += [re.sub(r"[*_]", "", quote).strip() for quote in collected["quotes"][key]]
        if collected["gaps"][key]:
            lines.append("Missing (do not mention): " + ", ".join(collected["gaps"][key]))
    return "\n".join(lines)


def _numbers(text: str) -> set[str]:
    return {n.replace(",", ".").rstrip("0").rstrip(".") if "." in n.replace(",", ".") else n for n in NUMBER.findall(text)}


def grounded(text: str, sheet: str) -> tuple[str, list[str]]:
    """Drop sentences that state numbers the fact sheet does not contain; return the text and the dropped sentences."""
    known = _numbers(sheet)
    kept, dropped = [], []
    for sentence in re.split(r"(?<=[.!?…])\s+", text.strip()):
        if not sentence:
            continue
        if _numbers(sentence) - known:
            dropped.append(sentence)
        else:
            kept.append(sentence)
    return " ".join(kept), dropped


def case_study_markdown(context: dict[str, Any], collected: dict[str, Any], draft: CaseStudyDraft | None) -> str:
    """Render the case study in the researched section order."""
    project = context["project"]
    words = _words(project["language"])
    title = draft.headline if draft and draft.headline else project["name"]
    lines = [f"# {title}", f"_{words['title']} · {project['name']}_", ""]
    for key, _, _ in GUIDE:
        lines += [f"## {words['sections'][key]}", ""]
        if key == "summary":
            meta = words["meta"]
            lines += [
                f"- **{meta['role']}:** {_gap(words, 'role')}",
                f"- **{meta['timeline']}:** {_gap(words, 'timeline')}",
                f"- **{meta['team']}:** {_gap(words, 'team')}",
                f"- **{meta['tools']}:** {words['tools']}",
                "",
            ]
        narrative = getattr(draft, key, "") if draft and key != "outcomes" else ""
        if narrative:
            lines += [narrative, ""]
        for quote in collected["quotes"][key][:3]:
            lines += [f"> {quote}", ""]
        body = collected["facts"][key]
        if body:
            lines += [line if line.startswith("  - ") else f"- {line}" for line in body]
            lines.append("")
        for gap in collected["gaps"][key]:
            if key == "summary" and gap in ("role", "timeline", "team"):
                continue
            lines += [f"- {_gap(words, gap)}"]
        if any(g not in ("role", "timeline", "team") for g in collected["gaps"][key]):
            lines.append("")
    if collected["sources"]:
        lines += [f"## {words['sections']['sources']}", ""]
        lines += [f"- {e['title'][:110]} — {e['url']}" for e in collected["sources"]]
        lines.append("")
    lines += ["---", words["footer"], ""]
    return "\n".join(lines)


class CaseStudyService:
    """Writes the case study next to the handoff pack, using the Deliver service's data and export folder."""

    def __init__(self, deliver: Any) -> None:
        self.deliver = deliver

    def context(self, project_id: int) -> dict[str, Any]:
        """Everything the case study may draw on, from Discover to the usability tests."""
        db = self.deliver.db
        context = self.deliver.report_context(project_id, self.deliver.state(project_id))
        nodes = db.list_nodes(project_id)
        context["nodes"] = nodes
        evidence = db.evidence_for_nodes([n["id"] for n in nodes], per_node=1000) if nodes else []
        context["evidence"] = list({e["id"]: e for e in evidence}.values())
        problem = context.get("problem") or {}
        ids = [*(problem.get("evidence_ids") or []), *(i for f in context.get("features", []) for i in (f.get("evidence_ids") or []))]
        context["cited"] = db.evidence_by_ids(list(dict.fromkeys(ids))) if ids else []
        return context

    async def generate(self, project_id: int, progress: ProgressFn, warn: WarnFn) -> dict[str, Any]:
        """Collect facts, let the model write grounded narrative, then save Markdown, HTML and PDF."""
        from .report import markdown_html, write_pdf

        progress(0.1, "context")
        context = self.context(project_id)
        project = context["project"]
        collected = case_study_facts(context)
        sheet = fact_sheet(context, collected)
        progress(0.3, "thinking")
        draft = None
        try:
            draft = await self.deliver.llm.structured(
                CaseStudyDraft,
                SYSTEM.format(language=LANGUAGE_NAMES.get(project["language"], "the project's language")),
                sheet,
                temperature=0.3,
            )
            draft = CaseStudyDraft.model_validate(draft.model_dump())
        except (OllamaError, ValueError, TypeError, AttributeError) as exc:
            warn(f"llm: {exc}")
            draft = None
        removed = []
        if draft is not None:
            for key, _, _ in GUIDE:
                if key == "outcomes":
                    continue
                text, dropped = grounded(getattr(draft, key), sheet)
                setattr(draft, key, text)
                removed += dropped
            headline, dropped = grounded(draft.headline, sheet)
            draft.headline = headline.rstrip(".")
            removed += dropped
        progress(0.8, "writing")
        markdown = case_study_markdown(context, collected, draft)
        directory: Path = self.deliver.export_dir(project)
        (directory / "case-study.md").write_text(markdown, encoding="utf-8")
        html_path = directory / "case-study.html"
        html_path.write_text(markdown_html(markdown, f"{_words(project['language'])['title']} — {project['name']}"), encoding="utf-8")
        files = ["case-study.md", "case-study.html"]
        if await write_pdf(html_path, directory / "case-study.pdf"):
            files.append("case-study.pdf")
        gaps = sum(len(v) for v in collected["gaps"].values())
        return {"markdown": markdown, "files": files, "directory": str(directory), "gaps": gaps, "removed": removed, "narrative": draft is not None}
