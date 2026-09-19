# Jev × Gamebook benchmark (Project Aon)

A small harness that turns a Project Aon Lone Wolf book into a typed-decision benchmark for **Jev**.

It deliberately does **not** bundle Project Aon's book text. Project Aon's Internet Editions have their own license and redistribution restrictions. The harness can read a local XML file or fetch the official XML at runtime after you have reviewed Project Aon's license.

## What v0 measures

Navigation only: at each numbered section, the environment extracts the narrative and all `<choice idref="...">` branches. Jev receives the current section, recent path, and optional player profile, then returns one typed `Choice` decision. For *Flight from the Dark*, the default benchmark target is section `350`.

This is useful before implementing full combat/inventory rules because it isolates the question: **can Jev repeatedly choose a promising legal branch from local narrative context and history?**

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Smoke test without Jev

```bash
pytest -q
```

### Download the official Project Aon XML at runtime + random baseline

```bash
python gamebook_jev.py --download --backend random --runs 100 --jsonl random.jsonl
```

The default XML URL is:

`https://www.projectaon.org/data/trunk/en/xml/01fftd.xml`

## Run with Jev directly

```bash
export JEV_API_KEY='...'
python gamebook_jev.py \
  --backend jev \
  --download \
  --profile-file profile.example.txt \
  --runs 20 \
  --jsonl jev.jsonl
```

The direct API request uses `POST https://api.typesafe.ai/v1/systemone` and the `Choice` primitive.

## Run Jev through OpenRouter

```bash
export OPENROUTER_API_KEY='...'
python gamebook_jev.py \
  --backend openrouter \
  --download \
  --profile-file profile.example.txt \
  --runs 20 \
  --jsonl jev-openrouter.jsonl
```

This uses OpenRouter's decisions endpoint (`/api/alpha/decisions`) rather than chat completions.

## Output

Every episode is one JSONL record containing:

- `status`: `success`, `deadend`, `loop`, `max_steps`, ...
- `path`: visited section numbers
- `steps`
- `mean_confidence`
- `mean_latency_ms`
- `trace`: per-step chosen action, target, full probability distribution, confidence, latency

That makes it easy to compare Jev vs random, or later vs an LLM controller.

## Important v0 limitation

This version does **not** yet execute Lone Wolf's Action Chart mechanics. It passes an optional textual player profile to Jev so it can avoid clearly illegal conditional choices, but it does not yet mutate inventory, Endurance, Gold, Kai disciplines, random-number outcomes, or combat state.

The next useful milestone is a strict `LoneWolfState` engine that parses or encodes:

1. prerequisite choices (discipline/item checks),
2. inventory/gold/meal changes,
3. random-number-table branches,
4. combat resolution,
5. death/victory conditions.

Once that exists, the benchmark becomes a true end-to-end "solve the book" test rather than a navigation benchmark.
