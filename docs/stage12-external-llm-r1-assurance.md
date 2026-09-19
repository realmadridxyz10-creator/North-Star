# Stage 12 External LLM R1 — Non-Live Assurance Record

Date: 2026-09-19
Branch: `stage-12-external-llm-r1`
Baseline branch: `stage-5.3-entra-oidc`
Baseline SHA: `3a0f16630f39af6b4e051a641ee8dd94bceefac3`
Production authorization: false

## Scope

R1 establishes and verifies the provider-neutral External LLM integration boundary without enabling any live external model, credential, SDK, billable request, or production authorization.

## Controlled implementation

- Added `app/external_llm.py` as a provider-neutral, fail-closed adapter contract.
- Preserved `LOCAL_EVIDENCE` as the governed fallback.
- Wired the non-live adapter into `/api/ai/ask` after North Star classification and governed evidence retrieval.
- Exposed non-live adapter state through `/api/ai/status`.
- Preserved R4/B1 as canonical authority and `canonical_content=false`.
- Existing Stage 11 runtime overlay continues to enforce Premium AI entitlement before the protected `/api/ai/ask` handler.
- No prompt/response body logging was introduced.

## Assurance evidence

- GitHub Actions Run #2: provider-neutral contract — PASS.
- Runs #3 and #4: workflow/test-environment failures while runtime dependencies were absent; no application defect established.
- GitHub Actions Run #5: contract plus governed AI runtime integration — PASS.
- GitHub Actions Run #6: expanded regression assurance — PASS.
- Final R1 regression verifies non-live status, local-mode isolation, safe external-request fallback, policy-attack boundary, governed citations, R4/B1 authority, and `production_authorized=false`.

## Change boundary

Compared with `stage-5.3-entra-oidc`, R1 changes are limited to:

- `.github/workflows/stage12-external-llm-contract.yml`
- `app/external_llm.py`
- `app/main.py`
- `tests/test_external_llm_contract.py`

No Stage 11 persistence, Entra, session, entitlement, DB-path, or Railway-volume implementation was changed.

## Closure

**Stage 12 External LLM R1 — Non-Live Governed Integration: PASS / CLOSED.**

R1 remains deliberately non-live. A later controlled stage is required before any provider selection, credential configuration, external network execution, Railway deployment, or production authorization.
