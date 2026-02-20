# Evaluation Report

## Dataset

- Test cases file: `data\eval_cases.json`
- Cases count: `10`
- Domain: smart contracts (English)

## Metrics

Run:

```bash
python -m app.evaluation --cases data/eval_cases.json
```

Recorded results:

- `answer_overlap`: `0.4469`
- `answer_f1`: `0.2541`
- `retrieval_hit_rate`: `0.7`
- `source_recall`: `0.55`
- `source_precision`: `0.7`
- `groundedness`: `0.908`
- `required_term_coverage`: `0.6667`
- `forbidden_term_violation_rate`: `0.0`
- `valid_case_rate`: `1.0`
- `success_rate`: `1.0`

## Findings

- Strong grounding (`0.908`) suggests answers are usually tied to retrieved context.
- Reliability of execution is high (`valid_case_rate=1.0`, `success_rate=1.0`).
- Source attribution is moderate (`retrieval_hit_rate=0.7`, `source_recall=0.55`, `source_precision=0.7`).
- Semantic answer quality is mixed (`answer_overlap=0.4469`, `answer_f1=0.2541`), so wording fidelity remains a gap.
- Required term coverage (`0.6667`) shows key details are often present but still missed in some answers.
- No forbidden-term violations (`0.0`) for the defined evaluation constraints.

## App Limitations

- Evaluation set is still small (10 cases) and may not represent all contract styles.
- Metrics are lexical/heuristic; they do not fully capture legal correctness or nuance.
- RAG quality depends on chunking and embedding quality; missed chunks reduce recall.
- Retrieval can surface partial context, which may produce incomplete answers.
- Citation scoring is filename-based and does not verify exact clause-level correctness.
- Local model fallback behavior may lower answer quality when stronger models are unavailable.
- Current workflow does not include automated human/legal review for high-stakes outputs.