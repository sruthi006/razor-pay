# Build phases

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Repo skeleton, placeholders | Completed |
| 1 | Domain grounding: decline taxonomy, schema, business rules, synthetic assumptions | In progress |
| 2 | Synthetic data generation | Not started |
| 3 | Baseline T+1/T+2/T+3 simulation | Not started |
| 4 | Features + first ML model | Not started |
| 5 | Confidence layer | Not started |
| 6 | Strategy comparison / evaluation | Not started |
| 7 | Streamlit dashboard + production notes | Not started |

Phase 1 artifacts:

- `src/decline_codes.py` — documented Razorpay `reason` names + prototype retry buckets
- `docs/data_schema.md` — row grain, fields, target, leakage
- `docs/business_rules.md` — eligibility, caps, candidate grid
- `docs/synthetic_data_assumptions.md` — intended DGP (not production facts)
