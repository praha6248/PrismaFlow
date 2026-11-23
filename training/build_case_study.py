"""Training pairs for the case study narrative: the app's fact sheet in, a fully grounded CaseStudyDraft out.

Facts come from synthetic projects over the training niches and from a copy of real PrismaFlow projects.
Every synthetic project goes through the app's own code: the Deliver audit, the usability test summary,
case_study_facts() and fact_sheet(). The target narrative is composed from those facts only, in the house
style measured on the licensed public-sector corpus (case_corpus.py): first person plural, short sentences,
findings stated plainly, numbers with their denominator, lessons and next steps at the end. Sections whose
data is missing get no claims about it. Each target passes the app's number filter with nothing removed and
the qualitative claim check in claims.py with no flags.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from backend.models import CaseStudyDraft, Flow
from backend.services.case_study import GUIDE, SYSTEM, _num, case_study_facts, fact_sheet, grounded
from backend.services.deliver import audit
from backend.services.discover import LANGUAGE_NAMES
from backend.services.usability import optimal_path, summarize

from claims import unsupported_claims
from flows import random_flow
from niches import EXTRAS, NICHES, TEST_SEEDS

DATA = ROOT / "data"
SEED = 20261123
PER_TRAIN_NICHE = 14
PER_TEST_NICHE = 5
REAL_TEST_PROJECTS = (5, 12, 13)

POOLS = {
    "pl": {
        "description": [
            "Problem wraca co tydzień i zniechęca do szukania lepszego rozwiązania.",
            "Dostępne narzędzia są zbyt ogólne, więc ludzie wracają do notatek i pamięci.",
            "Brakuje prostego sposobu, by zacząć bez długiej konfiguracji.",
            "Ludzie szukają porad na forach, bo nie ufają obecnym aplikacjom.",
        ],
        "quote": ["jak sobie poradzić, gdy {p}?", "{p} — co robić?", "Czy ktoś ma sposób na to: {p}?", "najlepsza aplikacja: {s}"],
        "hmw": ["Jak moglibyśmy ułatwić start osobom, którym zależy na tym: {f}?", "Jak moglibyśmy skrócić drogę do celu: {f}?", "Jak moglibyśmy zbudować zaufanie do rozwiązania w niszy „{s}”?"],
        "themes": [
            ("Brak czasu na konfigurację", "Użytkownicy chcą zacząć od razu, bez zakładania konta i wypełniania profilu."),
            ("Niejasne nazwy i ustawienia", "Etykiety w obecnych narzędziach nie mówią, co się stanie po kliknięciu."),
            ("Szukanie wiedzy na forach", "Wiedzę czerpią z grup i forów, bo aplikacje jej nie tłumaczą."),
            ("Koszt jako bariera", "Płatne rozwiązania odstraszają, zanim użytkownik zobaczy ich wartość."),
            ("Brak zaufania do automatyzacji", "Ludzie wolą sprawdzać wynik sami, niż polegać na automacie."),
            ("Potrzeba przypomnień", "Bez przypomnienia użytkownicy zapominają o regularnym działaniu."),
            ("Zbyt wiele opcji naraz", "Długie listy wyborów zniechęcają już na pierwszym ekranie."),
        ],
        "journey": [
            ("Szuka informacji", "Wyniki są sprzeczne"),
            ("Porównuje aplikacje", "Każda wymaga konta"),
            ("Konfiguruje ustawienia", "Niejasne nazwy opcji"),
            ("Sprawdza wynik", "Nie wie, czy wynik jest wiarygodny"),
            ("Wraca po tygodniu", "Zapomina, gdzie skończył"),
        ],
        "empathy": ["Chcę mieć to z głowy", "Czy to się opłaci?", "Sprawdza fora wieczorem", "Frustracja, gdy coś nie działa", "Pyta znajomych o radę", "Obawa przed utratą danych"],
        "notes": ["Nie mam czasu na zakładanie kolejnego konta.", "Szukałam tego w ustawieniach, nie wiedziałam, co znaczy ten przycisk.", "Wolę sprawdzić sama, niż ufać automatowi.", "Zapominam o tym, dopóki nie jest za późno.", "Płacić za to? Najpierw chcę zobaczyć, czy działa.", "Pytam na grupie, bo w aplikacji nic nie ma."],
        "hypothesis": ["Użytkownicy chcą zacząć bez konta", "Przypomnienia zwiększą regularność", "Ludzie ufają automatycznym zaleceniom", "Koszt jest główną barierą"],
        "people": ["Ania, 34", "Marek, 41", "Ola, 27", "Piotr, 52", "Kasia, 30"],
        "test_quotes": ["Nie wiedziałam, gdzie kliknąć dalej.", "Szukałem tego w ustawieniach.", "To było szybkie.", "Nie jestem pewna, czy to zapisało.", "Myślałem, że ten napis to przycisk."],
        "roots": {"niche": "nisza", "idea": "pomysł", "pain_point": "problem", "target_group": "grupa", "competitor": "konkurent"},
    },
    "en": {
        "description": [
            "The problem comes back every week and puts people off looking for a better way.",
            "Existing tools are too generic, so people fall back on notes and memory.",
            "There is no simple way to start without a long setup.",
            "People ask for advice in forums because they do not trust current apps.",
        ],
        "quote": ["how do I deal with {p}?", "{p} — any tips?", "Does anyone have a fix for this: {p}?", "best app for {s}"],
        "hmw": ["How might we make it easy to get {f} from day one?", "How might we shorten the path to {f}?", "How might we build trust in a solution for {s}?"],
        "themes": [
            ("No time for setup", "People want to start at once, without creating an account or filling in a profile."),
            ("Unclear labels and settings", "Labels in current tools do not say what happens after a tap."),
            ("Looking for know-how in forums", "People learn from groups and forums because apps do not explain things."),
            ("Cost as a barrier", "Paid tools put people off before they see the value."),
            ("Low trust in automation", "People would rather check the result themselves than rely on automation."),
            ("Need for reminders", "Without a reminder people forget to act regularly."),
            ("Too many options at once", "Long lists of choices put people off on the first screen."),
        ],
        "journey": [
            ("Looks for information", "Results contradict each other"),
            ("Compares apps", "Every one needs an account"),
            ("Configures settings", "Option names are unclear"),
            ("Checks the result", "Not sure the result can be trusted"),
            ("Comes back a week later", "Forgets where they left off"),
        ],
        "empathy": ["I just want it done", "Is it worth it?", "Reads forums in the evening", "Frustrated when things break", "Asks friends for advice", "Worried about losing data"],
        "notes": ["I don't have time for yet another account.", "I looked for it in settings, I didn't know what that button meant.", "I'd rather check myself than trust automation.", "I forget about it until it's too late.", "Pay for it? I want to see it work first.", "I ask in the group because the app has nothing."],
        "hypothesis": ["People want to start without an account", "Reminders will make people more regular", "People trust automatic recommendations", "Cost is the main barrier"],
        "people": ["Anna, 34", "Mark, 41", "Olivia, 27", "Peter, 52", "Kate, 30"],
        "test_quotes": ["I didn't know where to tap next.", "I looked for it in settings.", "That was quick.", "I'm not sure it saved.", "I thought that text was a button."],
        "roots": {"niche": "niche", "idea": "idea", "pain_point": "problem", "target_group": "group", "competitor": "competitor"},
    },
}


def chance(rng: random.Random, p: float) -> bool:
    return rng.random() < p


def synthetic_tests(flow: Flow, lang: str, rng: random.Random) -> dict[str, Any]:
    """Recorded sessions on the flow, summarised by the app's usability module."""
    screens = {s.id: s for s in flow.screens}
    goals = [s for s in flow.screens if s.kind == "goal"]
    steps = [s for s in flow.screens if s.kind == "step"]
    targets = goals[:1] + (rng.sample(steps, 1) if steps and chance(rng, 0.3) else [])
    tasks = [{"id": f"t{i + 1}", "goal": g.id, "scenario": ""} for i, g in enumerate(targets)]
    participants = rng.choice([2, 3, 4, 5, 5, 6, 8])
    quotes = POOLS[lang]["test_quotes"]
    sessions = []
    rates = {t["id"]: rng.choice([0.3, 0.5, 0.7, 0.9, 1.0, 1.0]) for t in tasks}
    for p in range(participants):
        results = []
        for task in tasks:
            optimal = optimal_path(flow, task["goal"])
            success = bool(optimal) and rng.random() < rates[task["id"]]
            path = list(optimal) if success else (optimal[: max(1, len(optimal) - 1)] if optimal else [flow.screens[0].id])
            if not success or chance(rng, 0.2):
                extra = rng.choice([s.id for s in flow.screens if s.id not in path] or [path[-1]])
                path = path[:-1] + [extra] + ([path[-1]] if success else [])
            misses = []
            for sid in path:
                dead = [e for e in screens[sid].elements if not e.target] if sid in screens else []
                if dead and chance(rng, 0.25):
                    misses.append({"screen": sid, "element": rng.choice(dead).label})
            results.append({
                "task": task["id"],
                "success": success,
                "seconds": round(rng.uniform(4, 45), 0),
                "path": path,
                "quote": rng.choice(quotes) if chance(rng, 0.35) else "",
                "misclicks": misses,
            })
        sessions.append({"id": f"x{p}", "participant": f"P{p + 1}", "results": results})
    return summarize(flow, {"tasks": tasks, "sessions": sessions})


def synthetic_context(niche: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    """A project at the end of Deliver with a random subset of phases filled in."""
    lang = niche["lang"]
    pool = POOLS[lang]
    seed = niche["seed"]
    name, role, focus = niche["persona"]
    features_pool = [(title, desc) for _, title, desc, _ in niche["screens"]]
    context: dict[str, Any] = {"project": {"id": 1, "name": seed, "seed": seed, "language": lang}}

    has_problem = chance(rng, 0.88)
    context["problem"] = None
    if has_problem:
        quote = rng.choice(pool["quote"]).format(p=niche["problem"].lower(), s=seed) if chance(rng, 0.7) else ""
        context["problem"] = {
            "title": niche["problem"],
            "description": rng.choice(pool["description"]),
            "quote": quote,
            "quote_source": rng.choice(["community", "autocomplete"]) if quote else None,
            "evidence_ids": [],
        }

    nodes = []
    if chance(rng, 0.85):
        nodes.append({"kind": "niche", "label": seed, "is_root": True, "starred": True})
        for kind, (low, high) in {"idea": (2, 8), "pain_point": (1, 5), "target_group": (1, 4), "competitor": (0, 3)}.items():
            for i in range(rng.randint(low, high)):
                label = rng.choice(features_pool)[0].lower() if kind == "idea" else f"{pool['roots'][kind]} {i + 1}"
                nodes.append({"kind": kind, "label": label, "is_root": False, "starred": chance(rng, 0.35)})
    context["nodes"] = nodes
    evidence = []
    if nodes and chance(rng, 0.85):
        counts = {"autocomplete": rng.randint(0, 80), "community": rng.randint(0, 30)}
        if chance(rng, 0.2):
            counts["trends"] = rng.randint(1, 6)
        evidence = [{"id": f"{src}{i}", "source": src} for src, n in counts.items() for i in range(n)]
    context["evidence"] = evidence

    validation = None
    if chance(rng, 0.35):
        hypotheses = []
        for text in rng.sample(pool["hypothesis"], rng.randint(1, 4)):
            status = rng.choice(["confirmed", "rejected", "open", "confirmed"])
            q = [{"quote": rng.choice(pool["notes"]), "person": rng.choice(pool["people"])}] if status != "open" and chance(rng, 0.6) else []
            hypotheses.append({"text": text, "status": status, "quotes": q})
        validation = {"hypotheses": hypotheses, "interviews": [{"person": p} for p in rng.sample(pool["people"], rng.randint(1, 5))]}
    context["validation"] = validation

    board = None
    if chance(rng, 0.7):
        themes = [{"id": f"t{i}", "name": n, "insight": ins if chance(rng, 0.8) else ""} for i, (n, ins) in enumerate(rng.sample(pool["themes"], rng.randint(2, 5)))]
        notes = []
        sources = ["interview", "note", "test", "evidence", "llm"] if validation else ["note", "test", "evidence", "llm", "interview"]
        weights = [4, 3, 2, 2, 1] if validation else [2, 2, 3, 3, 1]
        single = chance(rng, 0.3)
        for theme in themes:
            for _ in range(1 if single else rng.randint(1, 6)):
                notes.append({"text": rng.choice(pool["notes"]), "source": rng.choices(sources, weights)[0], "label": rng.choice(pool["people"]), "theme": theme["id"]})
        board = {"notes": notes, "themes": themes}
    context["board"] = board

    persona = None
    if chance(rng, 0.9):
        real = chance(rng, 0.25)
        persona = {
            "name": name,
            "age": rng.randint(22, 64),
            "role": role,
            "focus": focus,
            "quote": rng.choice(pool["notes"]),
            "profile": {"quote_source": "interview"} if real else {},
        }
    context["persona"] = persona

    empathy: dict[str, Any] = {}
    if chance(rng, 0.65):
        grounded_share = rng.choice([0.0, 0.5, 0.75, 1.0])
        for key in ("says", "thinks", "does", "feels"):
            empathy[key] = [{"text": rng.choice(pool["empathy"]), "from": ({"source": "interview"} if rng.random() < grounded_share else None)} for _ in range(rng.randint(2, 4))]
        journey = []
        for step, pain in rng.sample(pool["journey"], rng.randint(3, 5)):
            journey.append({"name": step, "emotion": rng.randint(-2, 2), "pain": pain, "action": step})
        empathy["journey"] = journey
    if chance(rng, 0.7):
        empathy["hmw_chosen"] = rng.choice(pool["hmw"]).format(f=focus, s=seed)
    context["empathy"] = empathy

    features = []
    if chance(rng, 0.85):
        for title, desc in rng.sample(features_pool, rng.randint(3, len(features_pool))):
            reach = rng.randint(2, 40)
            impact = rng.choice([0.5, 1.0, 2.0, 3.0])
            confidence = rng.choice([0.5, 0.8, 1.0, 1.0])
            effort = rng.choice([1.0, 2.0, 3.0, 5.0])
            features.append({
                "title": title,
                "description": desc,
                "priority": rng.choice(["must", "must", "should", "could"]),
                "rice": {"reach": reach, "impact": impact, "confidence": confidence, "effort": effort, "score": round(reach * impact * confidence / effort, 1)},
            })
    context["features"] = features

    flow = random_flow(niche, rng) if chance(rng, 0.85) else Flow()
    context["flow"] = flow.model_dump()
    context["audit"] = audit(flow) if flow.screens else {}
    context["tests"] = synthetic_tests(flow, lang, rng) if flow.screens and chance(rng, 0.7) else {"tasks": [], "sessions": [], "issues": [], "participants": 0}
    context["cited"] = []
    return context


class Writer:
    """Composes the narrative from the facts, picking one of several phrasings per sentence."""

    def __init__(self, context: dict[str, Any], collected: dict[str, Any], rng: random.Random) -> None:
        self.c = context
        self.f = collected
        self.rng = rng
        self.lang = "pl" if context["project"]["language"] == "pl" else "en"

    def pick(self, pl: list[str], en: list[str], **values: Any) -> str:
        return self.rng.choice(pl if self.lang == "pl" else en).format(**values)

    def n(self, value: float | int) -> str:
        return _num(value, self.lang)

    def tasks(self) -> list[dict[str, Any]]:
        return [t for t in (self.c.get("tests") or {}).get("tasks", []) if t.get("attempts")]

    def worst(self) -> dict[str, Any] | None:
        tasks = self.tasks()
        return min(tasks, key=lambda t: (t["successes"] / t["attempts"], -(t.get("seconds") or 0))) if tasks else None

    def issues(self, kind: str) -> list[dict[str, Any]]:
        return [i for i in ((self.c.get("tests") or {}).get("issues") or [])[:6] if i["kind"] == kind]

    def goal_name(self) -> str | None:
        path = ((self.c.get("audit") or {}).get("steps") or {}).get("path") or []
        if path:
            return path[-1]
        flow = Flow.model_validate(self.c.get("flow") or {"screens": []})
        goal = next((s for s in flow.screens if s.kind == "goal"), None)
        return goal.name if goal else None

    def who(self) -> str:
        persona = self.c.get("persona") or {}
        role = persona.get("role") or ""
        if role and len(role) <= 40 and not role.endswith("…"):
            return f"{persona['name']}, {role[:1].lower()}{role[1:]}"
        return persona.get("name", "")

    def focus(self) -> str:
        focus = ((self.c.get("persona") or {}).get("focus") or "").rstrip(".")
        return focus[:1].lower() + focus[1:]

    def headline(self) -> str:
        seed = self.c["project"]["seed"]
        persona = self.c.get("persona")
        features = sorted(self.c.get("features") or [], key=lambda f: -(f.get("rice") or {}).get("score", 0))
        options = []
        if persona and persona.get("focus"):
            options.append(f"{seed[:1].upper()}{seed[1:]}: {self.focus()}")
        if features:
            options.append(self.pick(["{t} — {s}"], ["{t} for {s}"], t=features[0]["title"], s=seed))
        if self.c.get("problem"):
            options.append(self.pick(["{s}: odpowiedź na problem: {p}"], ["{s}: tackling {p}"], s=seed[:1].upper() + seed[1:], p=self.c["problem"]["title"][:1].lower() + self.c["problem"]["title"][1:]))
        options = [o for o in options if len(o) <= 80]
        return self.rng.choice(options) if options else seed[:1].upper() + seed[1:]

    def summary(self) -> str:
        out = []
        problem, seed = self.c.get("problem"), self.c["project"]["seed"]
        if problem:
            out.append(self.pick(
                ["Punktem wyjścia był problem „{p}” w niszy „{s}”.", "Projekt dotyczy problemu „{p}”."],
                ["We started from one problem in {s}: “{p}”.", "This project tackles the problem “{p}”."],
                p=problem["title"], s=seed))
        flow = Flow.model_validate(self.c.get("flow") or {"screens": []})
        goal = self.goal_name()
        persona = self.c.get("persona")
        if flow.screens and goal:
            who = self.pick([" z myślą o personie: {w}", ""], [" for {w}", ""], w=self.who()) if persona else ""
            out.append(self.pick(
                ["Zaprojektowaliśmy przepływ prowadzący do ekranu „{g}”{w}.", "Powstał przepływ ekranów, który prowadzi do celu „{g}”{w}."],
                ["We designed a flow that leads to the “{g}” screen{w}.", "We designed a screen flow towards the goal “{g}”{w}."],
                g=goal, w=who))
        elif self.c.get("features"):
            out.append(self.pick(["Efektem jest uporządkowany backlog funkcji."], ["The result is a prioritised feature backlog."]))
        worst = self.worst()
        if worst:
            out.append(self.pick(
                ["W testach zadanie „{g}” ukończyło {s} z {a} osób.", "Test użyteczności pokazał, że zadanie „{g}” ukończyło {s} z {a} osób."],
                ["In testing, {s} of {a} people completed the task “{g}”.", "Usability testing showed that {s} of {a} people completed “{g}”."],
                g=worst["goal_name"], s=worst["successes"], a=worst["attempts"]))
        return " ".join(out)

    def context_text(self) -> str:
        out = []
        problem, persona = self.c.get("problem"), self.c.get("persona")
        hmw = (self.c.get("empathy") or {}).get("hmw_chosen")
        if problem and persona and persona.get("focus"):
            out.append(self.pick(
                ["Problem „{p}” uderza w to, na czym personie zależy najbardziej: {f}.", "{w} chce jednego: {f}; problem „{p}” stoi temu na drodze."],
                ["The problem “{p}” gets in the way of what matters most to the persona: {f}.", "{w} wants one thing: {f}; “{p}” stands in the way."],
                p=problem["title"], f=self.focus(), w=self.who()))
        elif problem:
            out.append(self.pick(
                ["Problem „{p}” sprawia, że ludzie w niszy „{s}” odkładają działanie na później."],
                ["The problem “{p}” makes people in {s} put things off."],
                p=problem["title"], s=self.c["project"]["seed"]))
        if hmw:
            out.append(self.pick(["Pytanie projektowe sformułowaliśmy tak: {h}", "Dlatego wybraliśmy pytanie: {h}"], ["We framed the design question as: {h}", "So we chose the question: {h}"], h=hmw.rstrip("?") + "?"))
        return " ".join(out)

    def research(self) -> str:
        out = []
        evidence = self.c.get("evidence") or []
        nodes = self.c.get("nodes") or []
        validation = self.c.get("validation") or {}
        interviews = validation.get("interviews") or []
        if evidence:
            sources = Counter(e["source"] for e in evidence)
            top, count = sources.most_common(1)[0]
            majority = count * 2 > len(evidence)
            if majority and top == "autocomplete":
                out.append(self.pick(
                    ["Większość sygnałów z sieci to podpowiedzi wyszukiwarki: pokazują, czego ludzie szukają, ale nie potwierdzają potrzeb."],
                    ["Most web signals are search suggestions: they show what people look for, not what they need."]))
            elif majority and top == "community":
                out.append(self.pick(
                    ["Większość sygnałów pochodzi z dyskusji w społecznościach, więc opisuje doświadczenia kilku osób, a nie całej grupy."],
                    ["Most signals come from community discussions, so they describe a few people's experience, not the whole group."]))
            else:
                out.append(self.pick(
                    ["Sygnały z sieci pokazują, czego ludzie szukają w tej niszy; to tropy, nie dowody."],
                    ["Web signals show what people look for in this niche; they are leads, not proof."]))
        elif nodes:
            out.append(self.pick(["Mapa Discover porządkuje pomysły, problemy i grupy docelowe tej niszy."], ["The Discover map lays out the ideas, problems and target groups of the niche."]))
        if interviews:
            hyps = validation.get("hypotheses") or []
            status = Counter(h.get("status", "open") for h in hyps)
            if status["rejected"]:
                out.append(self.pick(
                    ["W wywiadach część założeń upadła, co zawęziło kierunek projektu.", "Rozmowy obaliły część hipotez, więc nie budowaliśmy na nich dalej."],
                    ["Interviews disproved some assumptions, which narrowed the direction.", "The conversations rejected some hypotheses, so we did not build on them."]))
            elif status["confirmed"]:
                out.append(self.pick(
                    ["Wywiady potwierdziły część hipotez" + (", a pozostałe są nadal otwarte." if status["open"] else "."), ],
                    ["Interviews confirmed some hypotheses" + (", while the rest are still open." if status["open"] else "."), ]))
            else:
                out.append(self.pick(["Hipotezy po wywiadach są nadal otwarte."], ["After the interviews the hypotheses are still open."]))
        return " ".join(out)

    def synthesis(self) -> str:
        out = []
        board = self.c.get("board") or {}
        notes, themes = board.get("notes") or [], board.get("themes") or []
        if themes and notes:
            counts = {t["name"]: sum(1 for n in notes if n.get("theme") == t["id"]) for t in themes}
            values = list(counts.values())
            if max(values) <= 1:
                out.append(self.pick(
                    ["Każdy temat na tablicy opiera się na jednej notatce, więc traktujemy je jako tropy, a nie wnioski."],
                    ["Each theme on the board rests on a single note, so we treat them as leads rather than findings."]))
            else:
                top = max(counts, key=counts.get)
                if values.count(max(values)) == 1:
                    out.append(self.pick(
                        ["Najwięcej notatek zebrał temat „{t}”, więc od niego zaczęliśmy.", "Temat „{t}” ma najwięcej notatek i wyznaczył kierunek dalszej pracy."],
                        ["The theme “{t}” has the most notes, so we started there.", "“{t}” gathered the most notes and set the direction."],
                        t=top))
                else:
                    tied = [name for name, count in counts.items() if count == max(values)][:2]
                    out.append(self.pick(
                        ["Najwięcej notatek mają tematy „{a}” i „{b}”, więc to one wyznaczyły kierunek."],
                        ["“{a}” and “{b}” have the most notes, so they set the direction."], a=tied[0], b=tied[1]))
        empathy = self.c.get("empathy") or {}
        persona = self.c.get("persona")
        journey = empathy.get("journey") or []
        quadrants = [i for k in ("says", "thinks", "does", "feels") for i in empathy.get(k, [])]
        if quadrants and journey:
            worst = min(journey, key=lambda s: s.get("emotion", 0))
            who = persona["name"] if persona else self.pick(["persona"], ["the persona"])
            out.append(self.pick(
                ["Najtrudniejszy moment ścieżki, „{w}”, pokazuje, gdzie {p} najbardziej potrzebuje wsparcia.", "Na ścieżce najgorzej wypada etap „{w}”; tam projekt musi pomóc najbardziej."],
                ["The hardest moment of the journey, “{w}”, shows where {p} needs help most.", "The journey dips lowest at “{w}”, which is where the design must help most."],
                w=worst["name"], p=who))
        if quadrants:
            grounded_items = sum(1 for i in quadrants if i.get("from"))
            if grounded_items == 0:
                out.append(self.pick(["Mapa empatii nie ma jeszcze oparcia w notatkach ani wywiadach."], ["The empathy map is not yet backed by notes or interviews."]))
            elif grounded_items < len(quadrants):
                out.append(self.pick(["Część mapy empatii to wciąż założenia, a nie dane z badań."], ["Part of the empathy map is still assumption rather than research data."]))
            else:
                out.append(self.pick(["Każdy element mapy empatii ma źródło w badaniach."], ["Every item on the empathy map traces back to research."]))
        if persona and not (persona.get("profile") or {}).get("quote_source") and len(out) < 3 and chance(self.rng, 0.5):
            out.append(self.pick(["Cytat persony napisał model, więc nie traktujemy go jak wypowiedzi użytkownika."], ["The persona quote was written by the model, so we do not treat it as something a user said."]))
        return " ".join(out[:3])

    def ideation(self) -> str:
        features = self.c.get("features") or []
        if not features:
            return ""
        out = [self.pick(
            ["Backlog uporządkowaliśmy metodą MoSCoW, a kolejność w ramach priorytetów wyznaczył wynik RICE.", "Funkcje podzieliliśmy według MoSCoW i uszeregowaliśmy według RICE."],
            ["We sorted the backlog with MoSCoW and ranked features within each priority by RICE.", "We grouped features with MoSCoW and ranked them by RICE."])]
        ranked = sorted(features, key=lambda f: -(f.get("rice") or {}).get("score", 0))
        top = ranked[0]
        reaches = [(f.get("rice") or {}).get("reach", 0) for f in ranked[:5]]
        confidences = {round(100 * (f.get("rice") or {}).get("confidence", 0.5)) for f in ranked[:5]}
        if len(ranked) > 1 and (top.get("rice") or {}).get("score", 0) == (ranked[1].get("rice") or {}).get("score", 0):
            out.append(self.pick(["Kilka funkcji ma ten sam wynik RICE, więc o kolejności zdecyduje dalsze badanie."], ["Several features share the same RICE score, so further research will decide the order."]))
        elif (top.get("rice") or {}).get("reach", 0) == max(reaches):
            out.append(self.pick(["Na czele jest „{t}”, bo dociera do największej liczby osób."], ["“{t}” leads because it reaches the most people."], t=top["title"]))
        else:
            out.append(self.pick(["Na czele jest „{t}” z najwyższym wynikiem RICE."], ["“{t}” leads with the highest RICE score."], t=top["title"]))
        if confidences == {100} and len(ranked) > 1:
            out.append(self.pick(["Pewność wszędzie wynosi 100%, więc ranking zależy tylko od zasięgu, wpływu i nakładu."], ["Confidence is 100% everywhere, so the ranking depends only on reach, impact and effort."]))
        return " ".join(out)

    def design(self) -> str:
        flow = Flow.model_validate(self.c.get("flow") or {"screens": []})
        if not flow.screens:
            return ""
        a = self.c.get("audit") or {}
        out = []
        steps = a.get("steps") or {}
        path = steps.get("path") or []
        if steps.get("value") is not None and len(path) >= 2:
            out.append(self.pick(
                ["Ścieżka prowadzi od ekranu „{s}” do „{g}”.", "Droga do celu zaczyna się na ekranie „{s}” i kończy na „{g}”."],
                ["The path runs from “{s}” to “{g}”.", "The way to the goal starts on “{s}” and ends on “{g}”."],
                s=path[0], g=path[-1]))
        elif steps.get("value") is None:
            out.append(self.pick(["Audyt nie znalazł drogi od startu do celu, więc przepływ wymaga jeszcze połączeń."], ["The audit found no path from start to goal, so the flow still needs links."]))
        targets = a.get("targets") or {}
        total, aaa = targets.get("total", 0), targets.get("aaa", 0)
        if total:
            if aaa == total:
                out.append(self.pick(["Wszystkie cele dotykowe mają co najmniej 44 px."], ["All touch targets are at least 44 px."]))
            elif aaa == 0:
                out.append(self.pick(["Żaden cel dotykowy nie osiąga 44 px, więc powiększenie ich to pierwsza poprawka."], ["No touch target reaches 44 px, so enlarging them is the first fix."]))
            elif aaa * 2 <= total:
                out.append(self.pick(["Tylko {a} z {t} celów dotykowych ma co najmniej 44 px; mniejsze trzeba powiększyć."], ["Only {a} of {t} touch targets reach 44 px; the smaller ones need enlarging."], a=aaa, t=total))
            else:
                out.append(self.pick(["{a} z {t} celów dotykowych ma co najmniej 44 px, a pozostałe są mniejsze."], ["{a} of {t} touch targets reach 44 px; the rest are smaller."], a=aaa, t=total))
        dead = [d["screen"] for d in a.get("dead_ends") or []]
        crowded = list(dict.fromkeys(h["screen"] for h in a.get("hick", []) if h.get("warning")))
        if dead:
            out.append(self.pick(["Audyt wskazał ślepy zaułek na ekranie „{s}”."], ["The audit flagged a dead end on “{s}”."], s=dead[0]))
        elif crowded:
            out.append(self.pick(["Na ekranie „{s}” jest za dużo opcji naraz."], ["“{s}” offers too many choices at once."], s=crowded[0]))
        elif total and len(out) < 3:
            out.append(self.pick(["Audyt nie wykazał ślepych zaułków ani przeciążenia wyborem."], ["The audit found no dead ends and no choice overload."]))
        return " ".join(out[:3])

    def testing(self) -> str:
        tests = self.c.get("tests") or {}
        tasks = self.tasks()
        if not tests.get("participants") or not tasks:
            return ""
        out = []
        worst = self.worst()
        rate = worst["successes"] / worst["attempts"]
        if worst["successes"] == 0:
            out.append(self.pick(
                ["Nikt z {a} uczestników nie ukończył zadania „{g}”, więc droga do celu wymaga przebudowy."],
                ["None of the {a} participants completed “{g}”, so the way to the goal needs rework."],
                g=worst["goal_name"], a=worst["attempts"]))
        elif rate < 0.8:
            out.append(self.pick(
                ["Zadanie „{g}” ukończyło tylko {s} z {a} osób, więc droga do celu nie jest oczywista.", "Najsłabiej wypadło zadanie „{g}”: ukończyło je {s} z {a} osób."],
                ["Only {s} of {a} people completed “{g}”, so the way to the goal is not obvious.", "“{g}” was the weakest task: {s} of {a} people completed it."],
                g=worst["goal_name"], s=worst["successes"], a=worst["attempts"]))
        else:
            out.append(self.pick(
                ["Zadanie „{g}” ukończyło {s} z {a} osób."], ["{s} of {a} people completed “{g}”."],
                g=worst["goal_name"], s=worst["successes"], a=worst["attempts"]))
        slow = self.issues("slow")
        misclicks = self.issues("misclick")
        detours = self.issues("detour")
        if slow and (rate >= 0.8 or not misclicks):
            out.append(self.pick(
                ["Zadanie „{g}” trwało {r}× dłużej, niż przewiduje model KLM.", "Na zadanie „{g}” uczestnicy potrzebowali {r}× więcej czasu, niż przewiduje KLM."],
                ["“{g}” took {r}× longer than the KLM model predicts.", "People needed {r}× the time KLM predicts for “{g}”."],
                g=slow[0]["task"], r=self.n(slow[0]["ratio"])))
        if misclicks:
            labels = list(dict.fromkeys(f"„{m['element']}”" if self.lang == "pl" else f"“{m['element']}”" for m in misclicks))[:2]
            joined = (" i " if self.lang == "pl" else " and ").join(labels)
            if len(labels) == 1:
                out.append(self.pick(["Uczestnicy klikali {e}, choć ten element nic nie robi."], ["Participants tapped {e}, which does nothing."], e=joined))
            else:
                out.append(self.pick(["Uczestnicy klikali {e}, choć te elementy nic nie robią."], ["Participants tapped {e}, which do nothing."], e=joined))
        elif detours:
            out.append(self.pick(["Część osób zboczyła ze ścieżki na ekranie „{s}”."], ["Some people left the path on “{s}”."], s=detours[0]["screen"]))
        if tests["participants"] < 5:
            out.append(self.pick(["Przy {p} uczestnikach to sygnały, a nie twarde dane."], ["With {p} participants these are signals, not hard data."], p=tests["participants"]))
        return " ".join(out[:3])

    def reflection(self) -> str:
        out = []
        tasks = self.tasks()
        worst = self.worst()
        a = self.c.get("audit") or {}
        targets = a.get("targets") or {}
        clean = (a.get("steps") or {}).get("value") is not None and not a.get("dead_ends") and not any(h.get("warning") for h in a.get("hick", []))
        if worst and worst["successes"] / worst["attempts"] < 0.8:
            if clean:
                out.append(self.pick(
                    ["Test pokazał, że czysty audyt nie gwarantuje, że ludzie znajdą drogę do celu „{g}”.", "Najważniejsza lekcja: droga do celu „{g}” musi być widoczna od pierwszego ekranu."],
                    ["Testing showed that a clean audit does not guarantee people find their way to “{g}”.", "The main lesson: the way to “{g}” has to be visible from the first screen."],
                    g=worst["goal_name"]))
            else:
                out.append(self.pick(
                    ["Najważniejsza lekcja: droga do celu „{g}” musi być widoczna od pierwszego ekranu."],
                    ["The main lesson: the way to “{g}” has to be visible from the first screen."], g=worst["goal_name"]))
        misclicks = self.issues("misclick")
        slow = self.issues("slow")
        if slow and not out:
            out.append(self.pick(
                ["Choć zadanie „{g}” się udawało, trwało za długo, więc skrócimy drogę do celu."],
                ["Even when “{g}” succeeded it took too long, so we will shorten the path to the goal."], g=slow[0]["task"]))
        if misclicks:
            out.append(self.pick(["Elementy klikane bez efektu trzeba podpiąć albo usunąć."], ["Elements tapped with no effect need a target or should go."]))
        if targets.get("total") and targets.get("aaa", 0) < targets["total"]:
            out.append(self.pick(["Mniejsze cele dotykowe powiększymy do 44 px."], ["We will enlarge the smaller touch targets to 44 px."]))
        if tasks:
            out.append(self.pick(
                ["Po poprawkach powtórzymy test, najlepiej z większą liczbą uczestników.", "Kolejnym krokiem jest druga runda testów po poprawkach."],
                ["After the fixes we will run the test again, ideally with more participants.", "Next we will run a second test round after the fixes."]))
        elif (self.c.get("flow") or {}).get("screens"):
            out.append(self.pick(["Kolejnym krokiem jest test użyteczności przepływu z prawdziwymi użytkownikami."], ["Next we will run a usability test of the flow with real users."]))
        research = self.f["gaps"]["research"]
        if research and len(out) < 3:
            out.append(self.pick(["Warto też porozmawiać z osobami z grupy docelowej, bo dotąd wiedza pochodzi głównie z sieci."], ["We also need to talk to people in the target group, since our knowledge so far comes mostly from the web."]))
        if not out:
            out.append(self.pick(["Kolejnym krokiem jest dopracowanie przepływu i test z użytkownikami."], ["Next we will shape the flow and test it with users."]))
        return " ".join(out[:3])

    def draft(self) -> CaseStudyDraft:
        return CaseStudyDraft(
            headline=self.headline(),
            summary=self.summary(),
            context=self.context_text(),
            research=self.research(),
            synthesis=self.synthesis(),
            ideation=self.ideation(),
            design=self.design(),
            testing=self.testing(),
            reflection=self.reflection(),
        )


def example(context: dict[str, Any], rng: random.Random, tag: str) -> dict[str, Any] | None:
    """One chat example with the app's exact system prompt and fact sheet, or None if the target fails a check."""
    collected = case_study_facts(context)
    sheet = fact_sheet(context, collected)
    draft = Writer(context, collected, rng).draft()
    fields = draft.model_dump()
    dropped = [s for key, text in fields.items() for s in grounded(text, sheet)[1]]
    flags = unsupported_claims(fields, context)
    if dropped or flags or any(len(v) >= 600 for v in fields.values()):
        print("rejected", tag, dropped, flags)
        return None
    language = context["project"]["language"]
    return {
        "task": "case_study",
        "niche": context["project"]["seed"],
        "lang": language,
        "source": tag,
        "context": context,
        "messages": [
            {"role": "system", "content": SYSTEM.format(language=LANGUAGE_NAMES.get(language, "the project's language"))},
            {"role": "user", "content": sheet},
            {"role": "assistant", "content": json.dumps(fields, ensure_ascii=False)},
        ],
    }


def real_contexts(db_path: Path) -> dict[int, dict[str, Any]]:
    """Contexts of real projects from a backup copy of the PrismaFlow database."""
    from backend.database import Database
    from backend.services.case_study import CaseStudyService
    from backend.services.deliver import DeliverService

    service = CaseStudyService(DeliverService(Database(str(db_path)), None, export_root=db_path.parent / "exports"))
    ids = [row[0] for row in sqlite3.connect(db_path).execute("select id from projects order by id")]
    out = {}
    for pid in ids:
        context = json.loads(json.dumps(service.context(pid), default=str))
        if context.get("problem") or context.get("features") or (context.get("flow") or {}).get("screens"):
            out[pid] = context
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, help="backup copy of workspace.db (never the live file)")
    args = parser.parse_args()
    rng = random.Random(SEED)
    train, test = [], []
    for niche in NICHES:
        held_out = niche["seed"] in TEST_SEEDS
        target = test if held_out else train
        made = 0
        while made < (PER_TEST_NICHE if held_out else PER_TRAIN_NICHE):
            item = example(synthetic_context(niche, rng), rng, "synthetic")
            if item:
                target.append(item)
                made += 1
    if args.db:
        for pid, context in real_contexts(args.db).items():
            if pid in REAL_TEST_PROJECTS:
                item = example(context, rng, f"real:{pid}")
                if item:
                    test.append(item)
            else:
                for _ in range(2):
                    item = example(context, rng, f"real:{pid}")
                    if item:
                        train.append(item)
    DATA.mkdir(exist_ok=True)
    for name, rows in (("case_train.jsonl", train), ("case_test.jsonl", test)):
        with (DATA / name).open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    langs = Counter(r["lang"] for r in train)
    print(f"train {len(train)} ({dict(langs)}), test {len(test)} ({Counter(r['source'] for r in test)})")


if __name__ == "__main__":
    main()
