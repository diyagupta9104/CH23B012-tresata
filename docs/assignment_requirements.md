# Assignment requirements checklist

This checklist maps the finance assignment requirements to the repository.

## Core task

| Requirement | Evidence in this repository | Status |
|---|---|---|
| Define one finance problem, why it matters now, and what is out of scope | `docs/problem_brief.md`, section 1 | Complete |
| Explain the solution, inputs, AI role, outputs, human review, uncertainty, and why AI is useful | `docs/problem_brief.md`, section 2 | Complete |
| Think through architecture and alternatives | `docs/problem_brief.md`, sections 2–4; `submission/tresata_ai_use_log/architecture_and_edge_cases.md` | Complete |
| Prove the idea with at least 10 examples, if using the optional prototype | `samples/` contains 13 synthetic invoice PDFs; `reports/evaluation.json` records the results | Complete |
| Report failures honestly | `docs/problem_brief.md`, section 3; `reports/evaluation.json` known limits | Complete |

## Written brief

The submission brief is [problem_brief.pdf](problem_brief.pdf), with the editable source in [problem_brief.md](problem_brief.md). It covers:

- the finance area and surprising observation;
- the problem, user, task, frequency, cost, and boundary;
- the architecture and human/AI split;
- alternatives rejected and why;
- wrong answers, outdated rules, confidential data, liability, and mitigations;
- the next investigation before investing more time.

The PDF is limited to four pages. Confirm the rendered PDF page count once more before uploading.

## AI-use appendix

The one-page appendix is [ai_use_appendix.pdf](ai_use_appendix.pdf), with the editable source in [ai_use_appendix.md](ai_use_appendix.md). It covers where AI helped, what was rejected or corrected, what came from the candidate, and one design point to defend without tools.

Before submission, verify that the representative prompts match the candidate’s actual conversation history.

## Prototype or mock

The prototype is optional. If shared, use the repository link and [README.md](../README.md). The README explains how to run it, and [testing_guide.md](testing_guide.md) lists the examples and expected results. All bundled data is synthetic.

## LLM logs

The submission requires the actual AI conversation as a transcript or archive. The ZIP in `submission/tresata_ai_use_log.zip` contains supporting project AI-use material and an evidence index; attach the platform’s actual conversation export as the authoritative log. Do not invent missing turns.

## Data and accountability rules

- The prototype uses synthetic documents only.
- The scope is an Indian-rupee purchase-to-pay workflow; other jurisdictions would require different tax and policy rules.
- The system recommends a status; a qualified human remains accountable for payment and tax treatment.
- External model calls are optional and must be disabled for confidential data unless authorized.
