import streamlit as st
import json
import csv
from dotenv import load_dotenv
from openai import AsyncOpenAI
import os
import asyncio

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables. Please check your .env file.")
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# LLM Helpers

async def llm_call_async(prompt: str, model: str = "gpt-4o") -> str:
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error calling LLM: {str(e)}"

async def run_llm_parallel(prompt_details: list) -> list:
    tasks = [
        llm_call_async(item["user_prompt"], item["model"])
        for item in prompt_details
    ]
    return await asyncio.gather(*tasks)

# Prompt 1: Orchestrator 
def get_orchestrator_prompt(speech_segment: str) -> str:
    return f"""
You are Logos, an expert in logical analysis of political speeches.

You are given a segment from a Javier Milei speech. Your task is:
1. Identify the MAIN CONCLUSION Milei is trying to make in this segment.
2. Extract the individual claims he uses to build toward that conclusion.
3. Break them down into up to 3 sub-tasks, each representing a logical building block of his argument.

Respond ONLY with a JSON array in the following format (no additional text):
[
  {{
    "claim": "Specific claim extracted from the speech",
    "role": "premise | conclusion | supporting_evidence | rhetorical",
    "domain": "economy | inflation | employment | debt | politics | security | other",
    "description": "How this claim functions in Milei's overall argument"
  }}
]

If the segment contains NO logical structure (pure filler or disconnected sentences),
respond with an empty array: []

SPEECH SEGMENT:
{speech_segment}
"""

# Prompt 2: Worker

def get_worker_prompt(speech_segment: str, claim: str, domain: str, description: str) -> str:
    return f"""
You are an analyst specialized in fact-checking Argentine politics and economics.

You are assigned to verify ONE specific claim extracted from a Milei speech.

ORIGINAL SPEECH CONTEXT:
{speech_segment}

CLAIM TO VERIFY:
{claim}

DOMAIN: {domain}
WHAT TO CHECK: {description}

Your task:
1. Analyze the claim in detail.
2. Determine whether it is TRUE, FALSE, MISLEADING, or UNVERIFIABLE based on your knowledge
   of the Argentine economy and data available up to 2025.
3. Explain with concrete data (figures from INDEC, Central Bank, IMF, etc. where applicable).
4. Flag if the claim omits important context or is selectively true.

Structure your response as follows:
**Verdict:** TRUE | FALSE | MISLEADING | UNVERIFIABLE
**Analysis:** (2-3 paragraphs with concrete data)
**Omitted context:** (what relevant information Milei does not mention, if applicable)
**Suggested sources:** (INDEC, BCRA, IMF, Ministry of Economy, etc.)
"""

# Prompt 2.5: Formalizer

def get_formalizer_prompt(claim: str, worker_analysis: str) -> str:
    return f"""
You are a formal logic processor specialized in political argument analysis.
Your task is to translate a political claim into logical propositions and evaluate 
its internal consistency against real-world fact-checking.

CLAIM:
{claim}

FACT-CHECK ANALYSIS:
{worker_analysis}

Your task:
1. Identify the CONCLUSION the speaker is making.
2. Extract the individual PREMISES that support it (up to 4).
3. Formalize each into predicate logic notation (e.g. FiscalBalance(milei_mgmt)).
4. Determine if the conclusion logically follows from the premises (logical validity).
5. Cross-reference with the fact-check: is it Logically Valid but Factually False? Or both True?

Respond in this exact markdown structure:

### Formalization
**Conclusion:** (one sentence summary of what Milei is concluding)
**Conclusion Formula:** (predicate logic formula)

**Extracted Premises:**
- Premise1(subject)
- Premise2(subject)
- Premise3(subject)

**Solver Truth Value:** Logically Valid | Logically Invalid | Indeterminate

### Verdict
- **Logical consistency:** Valid | Invalid
- **Factual accuracy:** True | False | Misleading | Unverifiable
- **Final conclusion:** (one sentence combining both — e.g. "The argument is logically valid but factually misleading because...")
"""

# Prompt 3: Aggregator

def get_aggregator_prompt(speech_segment: str, claims: list, worker_responses: list, formalizer_responses: list) -> str:
    prompt = (
        "You are Logos, an expert in logical analysis of political discourse.\n"
        "You have fact-checks AND formal logic analyses for each claim in a Milei speech segment.\n"
        "Your task is to synthesize everything into a final report that analyzes both "
        "the factual accuracy AND the logical structure of his argument.\n\n"
        f"ORIGINAL SEGMENT:\n{speech_segment}\n\n"
        "ANALYSES PER CLAIM:\n"
    )

    for i, (claim_obj, worker, formalizer) in enumerate(
        zip(claims, worker_responses, formalizer_responses)
    ):
        prompt += f"\n{'─'*50}\n"
        prompt += f"Claim {i+1}: {claim_obj['claim']}\n"
        prompt += f"Role in argument: {claim_obj['role']}\n"
        prompt += f"Fact-check:\n{worker}\n"
        prompt += f"Logic formalization:\n{formalizer}\n"

    prompt += (
        f"\n{'─'*50}\n"
        "FINAL REPORT — instructions:\n"
        "1. **Argument Structure**: Map the logical flow — how does Milei move from premises to conclusion?\n"
        "2. **Logical Validity**: Do the premises actually support the conclusion? Flag any logical leaps or non-sequiturs.\n"
        "3. **Factual Accuracy**: Which claims are true, false, or misleading based on real data?\n"
        "4. **Fallacies Detected**: Identify any logical fallacies (e.g. false dichotomy, cherry-picking, appeal to fear).\n"
        "5. **Rhetorical Devices**: Note emotional language or framing used alongside factual claims.\n"
        "6. **Overall Verdict**: Is the argument logically sound AND factually accurate? Give a clear final judgment.\n\n"
        "Use markdown. Be precise and objective — Logos has no political position, it only analyzes logic and facts."
    )
    return prompt

# Main Workflow

async def run_logos_workflow(speech_segment: str):

    # ── Step 1: Orchestrator ──
    st.subheader("① Orchestrator — Identifying Claims & Argument Structure")
    orchestrator_prompt = get_orchestrator_prompt(speech_segment)

    with st.expander("View orchestrator prompt", expanded=False):
        st.code(orchestrator_prompt)

    with st.spinner("Orchestrator analyzing segment..."):
        orchestrator_response = await llm_call_async(orchestrator_prompt, model="gpt-4o")

    with st.expander("Orchestrator response (JSON)", expanded=True):
        st.code(orchestrator_response.replace("```json", "").replace("```", ""))

    try:
        claims = json.loads(
            orchestrator_response.replace("```json", "").replace("```", "").strip()
        )
    except json.JSONDecodeError:
        st.error("The orchestrator did not return valid JSON. Check the segment.")
        return

    if not claims:
        st.info("✓ This segment contains no verifiable claims (pure rhetoric).")
        return

    st.success(f"Identified **{len(claims)}** logical building blocks.")

    # ── Step 2: Workers ──
    st.subheader("② Workers — Parallel Fact-Checking")

    worker_prompt_details = [
        {
            "user_prompt": get_worker_prompt(
                speech_segment,
                claim["claim"],
                claim["domain"],
                claim["description"]
            ),
            "model": "gpt-4o"
        }
        for claim in claims
    ]

    with st.spinner("Workers verifying claims in parallel..."):
        worker_responses = await run_llm_parallel(worker_prompt_details)

    columns = st.columns(len(claims))
    for i, (col, claim, prompt_detail, response) in enumerate(
        zip(columns, claims, worker_prompt_details, worker_responses)
    ):
        with col:
            st.markdown(f"#### Claim {i+1}")
            st.markdown(f"**{claim['claim']}**")
            st.caption(f"Role: `{claim['role']}` | Domain: `{claim['domain']}`")
            with st.expander("View worker prompt", expanded=False):
                st.code(prompt_detail["user_prompt"])
            with st.expander("Fact-check analysis", expanded=True):
                st.markdown(response)

    # ── Step 2.5: Formalizer ──
    st.subheader("② ½ Formalizer — Logic & Predicate Analysis")

    formalizer_prompt_details = [
        {
            "user_prompt": get_formalizer_prompt(
                claim["claim"],
                worker_response
            ),
            "model": "gpt-4o"
        }
        for claim, worker_response in zip(claims, worker_responses)
    ]

    with st.spinner("Formalizing claims into logical propositions..."):
        formalizer_responses = await run_llm_parallel(formalizer_prompt_details)

    columns2 = st.columns(len(claims))
    for i, (col, claim, response) in enumerate(
        zip(columns2, claims, formalizer_responses)
    ):
        with col:
            st.markdown(f"#### Claim {i+1} — Logic")
            st.markdown(f"**{claim['claim']}**")
            with st.expander("Formal logic analysis", expanded=True):
                st.markdown(response)

    # ── Step 3: Aggregator ──
    st.subheader("③ Aggregator — Final Logic & Fact Report")

    aggregator_prompt = get_aggregator_prompt(
        speech_segment, claims, worker_responses, formalizer_responses
    )

    with st.expander("View aggregator prompt", expanded=False):
        st.code(aggregator_prompt)

    with st.spinner("Aggregator writing final report..."):
        final_report = await llm_call_async(aggregator_prompt, model="gpt-4o")

    st.markdown(final_report)

    # ── Export ──
    result = {
        "segment": speech_segment,
        "claims": claims,
        "worker_analyses": worker_responses,
        "formalizer_analyses": formalizer_responses,
        "final_report": final_report
    }
    st.download_button(
        "⬇ Download JSON Report",
        data=json.dumps(result, ensure_ascii=False, indent=2),
        file_name="logos_report.json",
        mime="application/json"
    )


@st.cache_data
def load_speeches(csv_path: str) -> list:
    segments = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("speaker") == "SPEAKER_00" and len(row["text"].strip()) > 80:
                segments.append({
                    "label": f"[{row['date']}] {row['title'][:60]}... ({row['text'][:60]}...)",
                    "text": row["text"].strip(),
                    "title": row["title"],
                    "date": row["date"],
                    "type": row["type"]
                })
    return segments

def main():
    st.set_page_config(page_title="Logos — Milei Fact-Checker", layout="wide")
    st.title("🔍 Logos — AI Logic & Fact-Checker for Milei Speeches")
    st.caption("Orchestrator → Parallel Workers → Formalizer → Aggregator")

    mode = st.radio("Input mode", ["Paste text manually", "Load from CSV"], horizontal=True)

    speech_segment = ""

    if mode == "Paste text manually":
        speech_segment = st.text_area(
            "Paste a Milei speech segment:",
            height=180,
            placeholder="e.g. 'We inherited an inflation rate of nearly 250% annually...'"
        )
    else:
        csv_path = st.text_input("CSV path", value="Milei_Hackathon_Transcriptions_2026.csv")
        if csv_path:
            try:
                segments = load_speeches(csv_path)
                selected = st.selectbox("Select segment:", [s["label"] for s in segments])
                speech_segment = next(s["text"] for s in segments if s["label"] == selected)
                st.info(speech_segment)
            except FileNotFoundError:
                st.error("CSV not found. Check the path.")

    if st.button("🚀 Run Logos", disabled=not speech_segment):
        asyncio.run(run_logos_workflow(speech_segment))

if __name__ == "__main__":
    main()