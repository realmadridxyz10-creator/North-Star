# Stage 12 External LLM R2 — Credential / Minimal Live UAT Preparation Gate

Date: 2026-09-19
Branch: `stage-12-external-llm-r2-readiness`
Status: PREPARATION BASELINE — NO LIVE REQUEST AUTHORIZED YET
Production authorization: false

## Entry evidence

- Provider nomination: OpenAI API / Responses API / `gpt-5.4-mini`.
- Provider-neutral fail-closed contract: PASS.
- Mock provider readiness: PASS.
- OpenAI transport + structured-response mock assurance: PASS (CI Run #8).
- Stage 11 remains frozen.

## Credential architecture

The live-UAT credential must be a dedicated OpenAI project API key used only by the North Star UAT server.

Required controls:

1. Create/use a dedicated OpenAI API project for North Star UAT rather than a personal/general-purpose project.
2. Keep API data sharing disabled.
3. Review the project's data-retention/ZDR eligibility before the first request.
4. Create a project-scoped secret key with the minimum practical permissions for Responses API execution.
5. Store the key only as Railway server-side variable `OPENAI_API_KEY`.
6. Never commit, paste into source, expose to browser JavaScript, return through an API response, or print it in logs.
7. Rotate/revoke the key after any suspected exposure and at the end of UAT if the project is not retained.

## UAT runtime variables

When the live-UAT implementation gate is approved, configure only:

- `NS_LLM_MODE=external`
- `NS_LLM_PROVIDER=OPENAI`
- `NS_LLM_MODEL=gpt-5.4-mini`
- `NS_LLM_TIMEOUT_SECONDS=20`
- `OPENAI_API_KEY=<Railway secret>`

Existing Stage 11 variables and controls must not be modified.

## Cost boundary

First live batch:
- maximum 20 external requests;
- synthetic/non-sensitive prompts only;
- no automated benchmark/load test;
- no background/recurring inference;
- stop on unexpected spend, routing, logging, or fallback behavior.

Before broader UAT, configure a project budget/usage alert or equivalent spend control.

## First live-UAT test sequence

Execute one control at a time:

1. Health check remains PASS and `production_authorized=false`.
2. AI status confirms the nominated external configuration without exposing the key.
3. Verify an unentitled request is rejected before external execution.
4. Verify a policy-attack request does not reach external synthesis.
5. Execute one benign synthetic grounded request.
6. Confirm external provider use is reported, `canonical_content=false`, and citations still originate from local R4/B1 evidence.
7. Execute a controlled provider-failure/timeout test and confirm fallback to `LOCAL_EVIDENCE`.
8. Inspect logs for absence of API key, Authorization header, prompt/response body, session cookie/token, and unnecessary PII.
9. Stop and reconcile evidence before any additional request batch.

## Immediate stop conditions

Stop live UAT immediately if:
- a secret appears in logs/output;
- an unentitled or policy-attack request reaches the provider;
- citations are accepted from provider output instead of local evidence;
- an invalid/ungrounded response bypasses fallback;
- `canonical_content` becomes true;
- `production_authorized` becomes true;
- Stage 11 session/entitlement behavior regresses;
- unexpected provider usage/cost occurs.

## Authorization boundary

This preparation document does not itself authorize a live request.

The next controlled implementation step is to add the live transport wiring using the already-tested OpenAI transport, while keeping it disabled unless all required environment variables are present. That wiring must pass CI before `OPENAI_API_KEY` is configured in Railway.
