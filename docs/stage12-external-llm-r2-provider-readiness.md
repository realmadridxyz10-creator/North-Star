# Stage 12 External LLM R2 — Provider Selection / Readiness Design

Date: 2026-09-19
Branch: `stage-12-external-llm-r2-readiness`
Status: DESIGN BASELINE — NO LIVE PROVIDER ENABLED
Production authorization: false

## Objective

Define the provider-selection gate before any credential, SDK, external network call, Railway deployment, or billable inference is introduced.

## North Star non-negotiable provider contract

Any selected provider must fit the existing governed pipeline:

1. Premium AI entitlement is enforced before the protected AI handler.
2. North Star classifies the question locally.
3. North Star retrieves bounded evidence from the governed R4/B1 corpus locally.
4. Only the minimum question/context and bounded evidence required for synthesis may cross the provider boundary.
5. The external model performs synthesis only; it is not a canonical retrieval authority.
6. The provider response must pass application-side response and grounding validation.
7. Citations remain generated from North Star's local governed evidence, not invented by the provider.
8. Any timeout, provider error, empty/invalid response, or grounding failure fails closed to `LOCAL_EVIDENCE`.
9. Generated wording remains `canonical_content=false`.
10. `production_authorized=false` remains unchanged until a separate production release gate.

## Security and privacy readiness requirements

Before live UAT, the provider path must support:

- server-side secret only; never expose provider credentials to browser/client;
- environment-specific credential and model configuration;
- explicit request timeout;
- no credential, prompt, response body, session cookie, token, or unnecessary PII logging;
- minimum-data request construction;
- no provider-managed conversation/file persistence unless separately reviewed and approved;
- documented provider retention/training terms for the selected commercial API;
- documented regional/data-residency implications where applicable;
- usage/cost controls and provider-side spend limits where available;
- deterministic application-side fallback to `LOCAL_EVIDENCE`.

## Response contract

The live provider integration must return a machine-validated synthesis result. At minimum the application must validate:

- non-empty answer;
- explicit grounding confirmation or equivalent application-verifiable grounding signal;
- no provider-supplied citation may become authoritative automatically;
- no generated response may be marked canonical;
- schema/semantic failure causes local fallback.

Structured output should be preferred where the selected provider/model supports it, but North Star application validation remains authoritative.

## Provider evaluation dimensions

A provider candidate must be evaluated against the same evidence-based dimensions:

- privacy / training treatment for commercial API data;
- retention controls and zero/modified retention eligibility;
- regional processing / residency options relevant to deployment;
- structured-output capability;
- timeout and error behavior suitable for fail-closed integration;
- model quality for evidence-bounded synthesis;
- latency;
- cost and spend-control capability;
- operational maturity and documentation;
- implementation complexity without weakening the provider-neutral adapter.

No weighted score or provider winner is recorded at this design stage.

## Candidate paths for controlled evaluation

Initial candidates for evidence collection are:

- OpenAI API
- Anthropic API
- Google Gemini API / Google Cloud path
- OpenRouter only as a routing option requiring both router and downstream-provider privacy review

The candidate list is not an approval and does not authorize credentials or live calls.

## Current decision

Provider selection remains **OPEN**.

The next gate is a documented candidate evidence matrix using current official provider documentation. Only after that matrix is reviewed and approved may one provider be nominated for a minimal live-UAT adapter.

## Change-control boundary

Until provider nomination is explicitly approved:

- do not add an API key;
- do not add a provider SDK;
- do not enable outbound inference;
- do not deploy R2 to Railway;
- do not change Stage 11 controls;
- do not change `production_authorized=false`.
