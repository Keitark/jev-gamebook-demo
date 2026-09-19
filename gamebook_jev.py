from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import requests
from lxml import etree

DEFAULT_AON_XML = "https://www.projectaon.org/data/trunk/en/xml/01fftd.xml"


def normalize_section_id(value: str) -> str:
    value = (value or "").strip().lstrip("#")
    m = re.fullmatch(r"(?:sect(?:ion)?[-_]?)?(\d+)", value, flags=re.I)
    return m.group(1) if m else value


def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def element_text(el: etree._Element) -> str:
    return clean_text(" ".join(t for t in el.itertext() if t))


@dataclass
class Choice:
    key: str
    target: str
    text: str


@dataclass
class Section:
    id: str
    text: str
    choices: List[Choice]
    deadend: bool = False
    combat: List[str] = field(default_factory=list)


class ProjectAonBook:
    """Small Project Aon XML reader for numbered sections.

    The Project Aon text is NOT bundled. Point this at a locally downloaded XML
    file, or use download_official_xml() to fetch it from Project Aon at runtime.
    """

    def __init__(self, sections: Dict[str, Section]):
        self.sections = sections

    @classmethod
    def from_file(cls, path: str | Path) -> "ProjectAonBook":
        parser = etree.XMLParser(
            recover=True,
            resolve_entities=False,
            load_dtd=False,
            no_network=True,
            huge_tree=True,
        )
        root = etree.parse(str(path), parser).getroot()
        return cls(cls._parse_sections(root))

    @staticmethod
    def _parse_sections(root: etree._Element) -> Dict[str, Section]:
        bases = root.xpath('.//*[local-name()="section" and @id="numbered"]')
        if bases:
            data_nodes = bases[0].xpath('./*[local-name()="data"]')
            candidates = data_nodes[0].xpath('./*[local-name()="section"]') if data_nodes else []
        else:
            candidates = root.xpath('.//*[local-name()="section" and @id]')

        sections: Dict[str, Section] = {}
        for sec in candidates:
            raw_id = sec.get("id", "")
            sid = normalize_section_id(raw_id)
            if not sid.isdigit():
                continue

            data_nodes = sec.xpath('./*[local-name()="data"]')
            data = data_nodes[0] if data_nodes else sec
            choice_nodes = data.xpath('.//*[local-name()="choice" and @idref]')

            choices: List[Choice] = []
            for i, ch in enumerate(choice_nodes):
                target = normalize_section_id(ch.get("idref", ""))
                txt = element_text(ch)
                choices.append(Choice(key=f"c{i}", target=target, text=txt or f"Turn to {target}"))

            pieces: List[str] = []
            for child in data:
                tag = etree.QName(child).localname if isinstance(child.tag, str) else ""
                if tag in {"choice", "deadend", "illustration"}:
                    continue
                t = element_text(child)
                if t:
                    pieces.append(t)

            deadend = bool(data.xpath('.//*[local-name()="deadend"]'))
            combats = []
            for c in data.xpath('.//*[local-name()="combat"]'):
                txt = element_text(c)
                if txt:
                    combats.append(txt)

            sections[sid] = Section(
                id=sid,
                text=clean_text(" ".join(pieces)),
                choices=choices,
                deadend=deadend,
                combat=combats,
            )

        if not sections:
            raise ValueError("No numbered sections found; Project Aon XML structure may have changed.")
        return sections


def download_official_xml(url: str, dest: str | Path) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest


@dataclass
class Decision:
    choice_key: str
    confidence: float
    probabilities: Dict[str, float]
    latency_ms: float
    raw: dict = field(default_factory=dict)


class Controller:
    def choose(self, state: str, choices: List[Choice]) -> Decision:
        raise NotImplementedError


class RandomController(Controller):
    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def choose(self, state: str, choices: List[Choice]) -> Decision:
        t0 = time.perf_counter()
        picked = self.rng.choice(choices)
        p = 1.0 / len(choices)
        return Decision(
            choice_key=picked.key,
            confidence=p,
            probabilities={c.key: p for c in choices},
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


class JevController(Controller):
    def __init__(
        self,
        api_key: str,
        endpoint: str = "https://api.typesafe.ai/v1/systemone",
        model: str = "jev-latest",
    ):
        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model

    def choose(self, state: str, choices: List[Choice]) -> Decision:
        criteria = {
            c.key: (
                "Take this available gamebook action when it is the best legal action for completing "
                "the adventure alive. Respect any condition stated in the action or current section. "
                f"Action: {c.text}"
            )
            for c in choices
        }
        payload = {
            "model": self.model,
            "state": state,
            "questions": {
                "route": {
                    "type": "choice",
                    "instructions": (
                        "Choose exactly one available action. Goal: complete the adventure, avoid death, "
                        "avoid pointless loops, conserve health/resources, and never choose an action whose "
                        "stated prerequisite is not satisfied by the supplied player state."
                    ),
                    "criteria": criteria,
                }
            },
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        t0 = time.perf_counter()
        r = requests.post(self.endpoint, headers=headers, json=payload, timeout=60)
        latency = (time.perf_counter() - t0) * 1000
        r.raise_for_status()
        data = r.json()
        ans = data["answers"]["route"]
        return Decision(
            choice_key=ans["choice"],
            confidence=float(ans.get("confidence", 0.0)),
            probabilities={k: float(v) for k, v in ans.get("probabilities", {}).items()},
            latency_ms=latency,
            raw=data,
        )


class OpenRouterJevController(JevController):
    def __init__(self, api_key: str, model: str = "typesafe/jev-1.13"):
        super().__init__(
            api_key=api_key,
            endpoint="https://openrouter.ai/api/alpha/decisions",
            model=model,
        )


@dataclass
class EpisodeResult:
    status: str
    final_section: str
    steps: int
    path: List[str]
    mean_confidence: float
    mean_latency_ms: float
    trace: List[dict]


class GamebookEnv:
    def __init__(
        self,
        book: ProjectAonBook,
        start: str = "1",
        goal: str = "350",
        profile: str = "No additional player-state information is supplied.",
        history_window: int = 12,
    ):
        self.book = book
        self.start = normalize_section_id(start)
        self.goal = normalize_section_id(goal)
        self.profile = profile
        self.history_window = history_window

    def build_state(self, section: Section, path: List[str]) -> str:
        history = " -> ".join(path[-self.history_window:])
        combat = "; ".join(section.combat) if section.combat else "none explicitly encoded"
        return (
            "GAME: Lone Wolf / Project Aon gamebook navigation benchmark\n"
            f"OBJECTIVE: Reach successful ending section {self.goal}.\n"
            f"PLAYER STATE: {self.profile}\n"
            f"RECENT PATH: {history}\n"
            f"CURRENT SECTION: {section.id}\n"
            f"COMBAT MARKUP IN THIS SECTION: {combat}\n"
            f"SECTION TEXT: {section.text}\n"
            "Important: section numbers are identifiers, not semantic hints. Decide from the narrative and player state."
        )

    def run(self, controller: Controller, max_steps: int = 200) -> EpisodeResult:
        current = self.start
        path = [current]
        trace: List[dict] = []
        confidences: List[float] = []
        latencies: List[float] = []

        for step in range(max_steps + 1):
            if current == self.goal:
                return self._result("success", current, step, path, confidences, latencies, trace)

            section = self.book.sections.get(current)
            if section is None:
                return self._result("missing_section", current, step, path, confidences, latencies, trace)
            if section.deadend:
                return self._result("deadend", current, step, path, confidences, latencies, trace)
            if not section.choices:
                return self._result("no_choice_terminal", current, step, path, confidences, latencies, trace)

            state = self.build_state(section, path)
            d = controller.choose(state, section.choices)
            choice_by_key = {c.key: c for c in section.choices}
            if d.choice_key not in choice_by_key:
                return self._result("invalid_model_choice", current, step, path, confidences, latencies, trace)

            chosen = choice_by_key[d.choice_key]
            confidences.append(d.confidence)
            latencies.append(d.latency_ms)
            trace.append({
                "step": step,
                "section": current,
                "choice": d.choice_key,
                "choice_text": chosen.text,
                "target": chosen.target,
                "confidence": d.confidence,
                "probabilities": d.probabilities,
                "latency_ms": d.latency_ms,
            })
            current = chosen.target
            path.append(current)

            if path.count(current) >= 6:
                return self._result("loop", current, step + 1, path, confidences, latencies, trace)

        return self._result("max_steps", current, max_steps, path, confidences, latencies, trace)

    @staticmethod
    def _result(status, current, steps, path, confidences, latencies, trace):
        mean_c = sum(confidences) / len(confidences) if confidences else 0.0
        mean_l = sum(latencies) / len(latencies) if latencies else 0.0
        return EpisodeResult(status, current, steps, path, mean_c, mean_l, trace)


def load_profile(args) -> str:
    if args.profile_file:
        return Path(args.profile_file).read_text(encoding="utf-8")
    if args.profile:
        return args.profile
    return "No inventory, disciplines, stats, or flags have been supplied; only choose actions that do not require known prerequisites."


def get_controller(args) -> Controller:
    if args.backend == "random":
        return RandomController(seed=args.seed)
    if args.backend == "jev":
        key = os.environ.get("JEV_API_KEY")
        if not key:
            raise SystemExit("Set JEV_API_KEY for --backend jev")
        return JevController(key, model=args.model or "jev-latest")
    if args.backend == "openrouter":
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise SystemExit("Set OPENROUTER_API_KEY for --backend openrouter")
        return OpenRouterJevController(key, model=args.model or "typesafe/jev-1.13")
    raise AssertionError(args.backend)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Run Jev against a Project Aon gamebook as a decision benchmark")
    p.add_argument("--xml", default="01fftd.xml", help="Local Project Aon XML path")
    p.add_argument("--download", action="store_true", help="Fetch the official XML at runtime if --xml is absent")
    p.add_argument("--url", default=DEFAULT_AON_XML)
    p.add_argument("--backend", choices=["jev", "openrouter", "random"], default="random")
    p.add_argument("--model", default=None)
    p.add_argument("--start", default="1")
    p.add_argument("--goal", default="350")
    p.add_argument("--max-steps", type=int, default=200)
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--profile", default=None)
    p.add_argument("--profile-file", default=None)
    p.add_argument("--jsonl", default="runs.jsonl")
    args = p.parse_args(argv)

    xml = Path(args.xml)
    if not xml.exists():
        if not args.download:
            p.error(f"{xml} not found. Download it yourself from Project Aon or add --download.")
        print(f"Downloading official Project Aon XML to {xml} ...", file=sys.stderr)
        download_official_xml(args.url, xml)

    book = ProjectAonBook.from_file(xml)
    print(f"Parsed {len(book.sections)} numbered sections", file=sys.stderr)
    env = GamebookEnv(book, start=args.start, goal=args.goal, profile=load_profile(args))

    out = Path(args.jsonl)
    results = []
    base_seed = args.seed
    with out.open("a", encoding="utf-8") as f:
        for run_idx in range(args.runs):
            if args.backend == "random":
                args.seed = base_seed + run_idx
            controller = get_controller(args)
            result = env.run(controller, max_steps=args.max_steps)
            record = {"run": run_idx, **result.__dict__}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            results.append(result)
            print(
                f"run={run_idx} status={result.status} steps={result.steps} "
                f"final={result.final_section} conf={result.mean_confidence:.3f} "
                f"latency={result.mean_latency_ms:.1f}ms"
            )

    successes = sum(r.status == "success" for r in results)
    print(f"success_rate={successes}/{len(results)} ({successes/len(results):.1%})")
    print(f"trace={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
