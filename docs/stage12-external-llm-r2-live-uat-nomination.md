# Stage 12 External LLM R2 — Minimal Live UAT Provider Nomination

Date: 2026-09-19
Branch: `stage-12-external-llm-r2-readiness`
Decision type: UAT NOMINATION — NOT PRODUCTION APPROVAL
Production authorization: false

## Nominated path

Provider: OpenAI API
API path: Responses API
Initial UAT model: `gpt-5.4-mini`
Purpose: bounded synthesis from North Star locally retrieved R4/B1 evidence only.

This nomination is limited to a minimal controlled UAT. It does not authorize production use.

## Why this path fits the existing North Star contract

The nominated path supports structured outputs and a direct provider integration, so North Star can preserve its provider-neutral adapter while keeping retrieval, canonical evidence, entitlement enforcement, citations, and fallback under application control.

Current official OpenAI documentation states that API/business data is not used to train models by default unless the customer opts in. Qualifying API organizations can use Zero Data Retention controls. UAE data residency at rest is available to eligible customers; current documentation indicates in-region API processing is supported in the US and Europe rather than UAE.

The selected UAT model supports Structured Outputs and is intended for efficient high-volume workloads. Current published token pricing is USD 0.75 per 1M input tokens and USD 4.50 per 1M output tokens. Pricing must be rechecked before production approval.

## Required UAT configuration

Environment variables to be introduced only at the credential/configuration gate:

- `NS_LLM_MODE=external`
- `NS_LLM_PROVIDER=OPENAI`
- `NS_LLM_MODEL=gpt-5.4-mini`
- `NS_LLM_TIMEOUT_SECONDS=20`
- `OPENAI_API_KEY=<server-side secret>`

The API key must never be committed to GitHub, returned to the browser, or printed in logs.

## Request boundary

North Star may send only:

- the user's current question;
- the locally determined answer class;
- the minimum bounded R4/B1 evidence required for synthesis;
- fixed North Star synthesis instructions;
- a structured response schema.

North Star must not send:

- session cookies/tokens;
- Entra credentials/claims not required for synthesis;
- entitlement database rows;
- user profile data not necessary for the answer;
- arbitrary application logs;
- full corpus/files when bounded evidence is sufficient.

No provider web search, file search, conversation memory, remote retrieval, or external grounding tool is authorized for this UAT.

## Response contract

The provider response must be machine-validated before use.

Minimum application contract:

- `answer`: non-empty string;
- `grounded`: boolean and must be true.

North Star citations remain derived from the local evidence objects. Provider-generated citation identifiers or external sources must not become canonical evidence.

Every external answer remains:

- `canonical_content=false`;
- governed by R4/B1 as canonical authority.

## Fail-closed conditions

The request must fall back to `LOCAL_EVIDENCE` on:

- timeout;
- HTTP/provider error;
- authentication/configuration error;
- empty answer;
- malformed/schema-invalid response;
- grounding not confirmed;
- unavailable model;
- application validation failure.

No external failure may bypass the existing local response path.

## Privacy gate before first live request

Before the first live UAT request, verify in the selected OpenAI API organization/project:

1. API data sharing remains disabled.
2. Zero Data Retention status/eligibility is confirmed where available for the selected endpoint/project.
3. No feature incompatible with the intended retention posture is enabled.
4. The selected project/region configuration is documented.
5. Only synthetic/non-sensitive UAT prompts are used for the first live tests.

If ZDR is not available to the project, the first live UAT may proceed only with synthetic/non-sensitive North Star test prompts after explicit approval, under the documented standard API retention controls.

## Cost control

Minimal live UAT ceiling:

- maximum 20 controlled external requests for the first execution batch;
- no automated load/performance test;
- no background or recurring calls;
- bounded evidence and bounded output;
- stop immediately on unexpected usage/cost behavior.

A provider-side project budget/usage alert or equivalent cost control should be configured before broader UAT.

## Acceptance criteria

Minimal live UAT can PASS only when evidence demonstrates:

1. Premium AI entitlement remains enforced before external execution.
2. A valid grounded request can use the nominated provider.
3. Citations still originate from local R4/B1 evidence.
4. Policy-attack requests do not reach external synthesis.
5. Timeout/provider failure returns safe `LOCAL_EVIDENCE` fallback.
6. Invalid/ungrounded response returns safe local fallback.
7. No secret or prompt/response body is leaked to logs.
8. `canonical_content=false` and `production_authorized=false` remain intact.
9. Stage 11 session, entitlement, DB and Entra controls remain unchanged.

## Explicitly not authorized yet

This nomination does NOT yet authorize:

- adding `OPENAI_API_KEY` to Railway;
- installing or calling the OpenAI SDK/API;
- deploying R2 to Railway;
- executing a billable request;
- changing Stage 11 controls;
- production use.

## Gate result

**OpenAI API / Responses API / gpt-5.4-mini is NOMINATED for minimal live UAT.**

Next controlled gate: implement the OpenAI transport adapter and structured-response validation behind mocks/tests first, with no credential and no network execution. Only after that implementation passes CI should credential configuration and the first live UAT request be considered.
