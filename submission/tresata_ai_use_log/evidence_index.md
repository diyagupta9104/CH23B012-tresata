# Evidence index

This index points to files in the repository that support the reconstructed log.

| Claim | Repository evidence |
|---|---|
| Problem, scope, architecture, risks, and limitations | `docs/problem_brief.md` and `docs/problem_brief.pdf` |
| One-page AI disclosure draft | `docs/ai_use_appendix.md` and `docs/ai_use_appendix.pdf` |
| Run instructions and prototype behavior | `README.md` |
| Detailed test routes and expected outcomes | `docs/testing_guide.md` |
| 13-case observed evaluation | `reports/evaluation.json` |
| Combination and replay checks | `reports/combinations.json` |
| PDF extraction and OCR implementation | `engine/extraction.py` |
| Deterministic workflow and audit history | `engine/workflow.py` |
| Policy and purchase-order calculations | `engine/config.py` |
| Streamlit screens and local interaction flow | `app.py` |
| Synthetic input corpus | `samples/`, `sample_orders/`, and `sample_evidence/` |

The repository evidence supports implementation claims. It does not prove the exact wording of missing chat turns. For that reason, the reconstruction must remain labeled as a reconstruction until the original conversation export is attached.
