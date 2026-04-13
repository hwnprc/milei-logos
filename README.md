# 🔍 Logos — AI Fact-Checker for Milei Speeches

> Multi-agent pipeline that breaks political speech into logical claims, fact-checks each one in parallel, formalizes them in predicate logic, and synthesizes a final verdict.

---

## Architecture

```
Speech Segment
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  ① ORCHESTRATOR                                     │
│  Parses segment → extracts up to 3 logical claims   │
│  Labels each: role (premise/conclusion/rhetorical)  │
│  and domain (economy/inflation/debt/politics/...)   │
└──────────────────────────┬──────────────────────────┘
                           │  JSON array of claims
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌────────────┐   ┌────────────┐   ┌────────────┐
   │ ② WORKER  │   │ ② WORKER  │   │ ② WORKER  │  ← parallel
   │ Claim 1   │   │ Claim 2   │   │ Claim N   │    asyncio
   │           │   │           │   │           │    .gather
   │ TRUE /    │   │ FALSE /   │   │ MISLEADING│
   │ FALSE /   │   │ MISLEADING│   │ /UNVERIF. │
   │ MISLEAD.. │   │ /UNVERIF. │   │           │
   └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
         │               │               │
         ▼               ▼               ▼
   ┌────────────┐   ┌────────────┐   ┌────────────┐
   │ ②½ FORMAL │   │ ②½ FORMAL │   │ ②½ FORMAL │  ← parallel
   │ Predicate │   │ Predicate │   │ Predicate │
   │ logic +   │   │ logic +   │   │ logic +   │
   │ validity  │   │ validity  │   │ validity  │
   └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
          └────────────────┼────────────────┘
                           ▼
┌─────────────────────────────────────────────────────┐
│  ③ AGGREGATOR                                       │
│  Synthesizes all fact-checks + logic into a report  │
│  Flags fallacies, rhetorical devices, final verdict │
└─────────────────────────────────────────────────────┘
                           │
                     📄 JSON export
```

---

## Key Design Decisions

**Orchestrator as argument parser, not claim lister** — instead of extracting raw sentences, it maps the logical *structure* of the argument (what's a premise, what's the conclusion, what's rhetorical filler). This makes downstream analysis meaningful rather than mechanical.

**Workers run in parallel** — each claim is fact-checked independently via `asyncio.gather`. No claim waits for another. Latency scales with the longest single call, not the number of claims.

**Two-track verification (fact + logic)** — a claim can be *logically valid* but *factually false*. Separating the Formalizer from the Worker makes this distinction explicit rather than collapsing it into a single verdict.

**Aggregator sees everything** — the final stage receives the original segment, all claims with their roles, all fact-checks, and all logic formalizations. This gives it enough context to detect fallacies that only emerge when claims are read *together* (e.g. false dichotomy, non-sequitur).

**Temperature = 0 throughout** — every LLM call uses `temperature=0` for reproducibility. Same segment in, same analysis out.

---

## Verdicts

| Layer | Possible outputs |
|-------|-----------------|
| Fact-check (Worker) | `TRUE` · `FALSE` · `MISLEADING` · `UNVERIFIABLE` |
| Logic (Formalizer) | `Logically Valid` · `Logically Invalid` · `Indeterminate` |
| Final (Aggregator) | Combined judgment + fallacies + rhetorical devices |

---

## Setup

```bash
pip install streamlit openai python-dotenv
```

Add a `.env` file:
```env
OPENAI_API=your_openai_api_key
```

Run:
```bash
streamlit run app.py
```

Input: paste a speech excerpt manually, or load from a CSV with columns `speaker`, `text`, `title`, `date`, `type` (filters on `SPEAKER_00`).

---

## Output

```json
{
  "segment": "...",
  "claims": [{ "claim": "...", "role": "premise", "domain": "economy" }],
  "worker_analyses": ["**Verdict:** FALSE ..."],
  "formalizer_analyses": ["### Formalization ..."],
  "final_report": "..."
}
```

---

*Logos has no political position — it only analyzes logic and facts.*
