# Stage 12 External LLM R2 — Provider Candidate Evidence Matrix

Date: 2026-09-19
Branch: `stage-12-external-llm-r2-readiness`
Status: EVIDENCE BASELINE — PROVIDER SELECTION OPEN
Production authorization: false

## Purpose

This matrix records current official-source evidence for the provider-selection gate. It does not approve a provider, credential, SDK, live call, or Railway deployment.

| Control dimension | OpenAI API | Anthropic API | Google Gemini / Vertex AI | OpenRouter |
|---|---|---|---|---|
| Commercial/API data used for model training | API data is not used to train/improve OpenAI models unless the customer explicitly opts in. | Anthropic states retained commercial/API data is not used for model training without express permission. | Google states paid Gemini API prompts/responses are not used to improve products; Vertex AI states customer data is not used to train/fine-tune models without permission/instruction. | Router behavior depends on selected downstream provider; OpenRouter requires review of each provider's data practices and offers data-collection routing controls. |
| Default / standard retention | OpenAI API abuse-monitoring logs may retain customer content up to 30 days by default; some stateful endpoints have additional application-state retention. | Standard Anthropic API inputs/outputs are automatically deleted within 30 days, subject to exceptions; current Claude Platform docs document feature/model-specific retention. | Gemini paid services have limited retention scenarios including abuse monitoring; some features such as Search/Maps grounding retain data for 30 days. Vertex AI has feature-specific retention conditions. | OpenRouter and downstream-provider retention both matter. Provider listings expose retention characteristics; routing must be constrained for governed use. |
| Zero Data Retention path | Available to qualifying/approved API organizations. Endpoint/feature eligibility must be checked. | ZDR is available by arrangement/approval for eligible API organizations/features. Some features/models are not ZDR eligible. | Gemini Developer API requires feature/configuration choices for ZDR; Google recommends Vertex AI for enterprise-grade ZDR requirements. Vertex AI documents steps/conditions for ZDR. | Can enforce ZDR through account settings, guardrails, or per-request `provider.zdr=true`, but only eligible downstream endpoints are used. |
| Regional / residency controls | Data residency is project-configurable for eligible customers. UAE regional storage is documented; UAE currently does not provide regional inference processing and requires approval plus ZDR/modified-abuse-monitoring controls. | Claude documents independent inference-geo and workspace-geo controls; availability depends on model/platform/geography. | Vertex AI supports location/data-residency controls for supported services/models. Exact deployment region must be validated at implementation time. | Current sovereign in-region documentation specifically describes EU routing. No UAE in-region routing evidence was identified in the reviewed official documentation. |
| Structured output | Native JSON-schema Structured Outputs are documented. | Structured Outputs provide schema conformance; under ZDR the schema may be cached separately for up to 24 hours. | Vertex AI supports controlled generation using response MIME type and response schema. | Supports JSON-schema structured outputs for compatible downstream models/providers. |
| Application-side grounding suitability | Suitable for North Star bounded-evidence synthesis; local evidence/citation authority must remain application-controlled. | Suitable for bounded-evidence synthesis; local evidence/citation authority must remain application-controlled. | Suitable for bounded-evidence synthesis; North Star should not enable Google Search/Maps grounding because North Star R4/B1 remains the canonical evidence authority. | Technically suitable, but adds a router plus downstream-provider governance boundary. Provider/model routing must be pinned/controlled. |
| Cost/spend governance | Platform/project usage controls must be configured and verified before live UAT. | Workspace/API usage controls must be configured and verified before live UAT. | Google Cloud project/billing controls must be configured and verified before live UAT. | Guardrails support USD spending limits plus model/provider allowlists; API-key limits also apply. |
| Integration complexity for North Star | Direct provider integration; one external processor boundary. | Direct provider integration; one external processor boundary. | Direct provider integration; Vertex path introduces Google Cloud project/IAM/location configuration. | Unified interface but introduces an additional routing/governance layer and downstream-provider dependency. |
| Current North Star status | Candidate only | Candidate only | Candidate only | Candidate only |

## North Star interpretation

### OpenAI API
Strengths supported by current documentation:
- commercial API data is not used for training by default;
- ZDR is available for qualifying organizations;
- native strict JSON-schema output is available;
- UAE regional storage is documented.

Control note:
- UAE currently provides regional storage but not regional processing according to the reviewed data-controls table.
- ZDR eligibility varies by endpoint/feature; stateful/background features must be avoided unless separately approved.

### Anthropic API
Strengths supported by current documentation:
- ZDR arrangements are available for eligible API organizations;
- Messages API and Structured Outputs can be ZDR eligible;
- structured outputs provide schema conformance;
- explicit inference/workspace geography controls are documented.

Control note:
- standard retention and model/feature exceptions must be checked for the exact selected model.
- structured-output schemas may be cached up to 24 hours under ZDR; North Star schemas must contain no user-specific/sensitive data.

### Google Gemini / Vertex AI
Strengths supported by current documentation:
- paid Gemini API data is not used to improve Google products;
- Vertex AI states customer data is not used to train/fine-tune models without permission;
- ZDR and data-residency controls are documented;
- response-schema controlled generation is supported.

Control note:
- North Star should avoid provider web/search grounding because R4/B1 must remain the evidence authority.
- Gemini Developer API and Vertex AI have different enterprise/privacy control surfaces; a final Google nomination must specify which one.

### OpenRouter
Strengths supported by current documentation:
- provider/model routing flexibility;
- ZDR and data-collection-deny controls;
- model/provider allowlists and spending guardrails;
- structured outputs for compatible endpoints.

Control note:
- OpenRouter adds a second governance boundary: both router and downstream provider practices apply.
- current official sovereign routing evidence reviewed here identifies EU in-region routing, not UAE in-region routing.
- any North Star use would require provider pinning/allowlisting, ZDR enforcement, data_collection=deny, model allowlisting, and spend caps.

## Evidence sources reviewed

OpenAI:
- https://platform.openai.com/docs/models/default-usage-policies-by-endpoint
- https://openai.com/business-data/
- https://openai.com/index/offering-zero-data-retention-for-frontier-models/

Anthropic:
- https://platform.claude.com/docs/en/manage-claude/api-and-data-retention
- https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- https://platform.claude.com/docs/en/manage-claude/data-residency
- https://privacy.anthropic.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data

Google:
- https://ai.google.dev/gemini-api/docs/zdr
- https://docs.cloud.google.com/vertex-ai/generative-ai/docs/vertex-ai-zero-data-retention
- https://docs.cloud.google.com/vertex-ai/generative-ai/docs/security-controls
- https://docs.cloud.google.com/vertex-ai/generative-ai/docs/samples/generativeaionvertexai-gemini-controlled-generation-response-schema-2

OpenRouter:
- https://openrouter.ai/privacy/
- https://openrouter.ai/providers/
- https://openrouter.ai/docs/guides/features/structured-outputs
- https://openrouter.ai/docs/guides/get-started/sovereign-ai
- https://openrouter.ai/docs/guides/features/guardrails/overview

## Gate result

**Provider Candidate Evidence Matrix: COMPLETE.**

Provider nomination remains OPEN. Before live UAT, the selected candidate must have:
1. exact API/platform path;
2. exact model;
3. exact retention/ZDR status for that model and endpoint;
4. regional-processing/storage decision;
5. server-side secret name and rotation method;
6. structured response schema;
7. timeout and fallback values;
8. cost/spend ceiling;
9. explicit confirmation that no Stage 11 control is weakened.

No live provider action is authorized by this document.
