# Evaluation Report

## Dataset

- Test cases file: `data/eval_cases.json`
- Domain: smart contracts (English)

## Metrics

Run:

```bash
python -m app.evaluation --cases data/eval_cases.json
```

Record results:

- `answer_overlap`: _TBD_
- `answer_f1`: _TBD_
- `retrieval_hit_rate`: _TBD_
- `source_recall`: _TBD_
- `source_precision`: _TBD_
- `groundedness`: _TBD_
- `required_term_coverage`: _TBD_
- `forbidden_term_violation_rate`: _TBD_
- `valid_case_rate`: _TBD_
- `success_rate`: _TBD_

## Findings

- Strengths: grounded responses with explicit citations.
- Weaknesses: quality depends on chunking and retrieval relevance.

## Limitations

- Sample-size evaluation only.
- Metric quality depends on expected answer/source quality.
- Local model quality can vary by hardware and model availability.

## Improvement Plan

1. Expand evaluation set with diverse contract formats.
2. Add reranking for top-k retrieval results.
3. Add answer faithfulness checking via LLM-as-judge.
