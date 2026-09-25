# NORTH STAR — Stage 14 Production Readiness Closure

**Project:** NORTH STAR — The Executive Guide to Enterprise Technology, Leadership & Transformation  
**Stage:** 14 — Production Readiness  
**Branch:** `stage-14-production-readiness`  
**Closure Date:** 25 September 2026  
**Final Status:** PASS / CLOSED  

---

## 1. Control Principle

Stage 14 was executed under the standing North Star control:

> Evidence before PASS.

No authentication, persistence, entitlement, external-LLM, security, or production-authorization control was weakened in order to obtain a successful result.

Production authorization remains disabled in the UAT environment.

---

## 2. Stage 14.1 — CI Baseline

The Stage 12 External LLM R1 Contract workflow was enabled for:

`stage-14-production-readiness`

Initial Stage 14 CI baseline:

- Workflow: `Stage 12 External LLM R1 Contract`
- Run: `#39`
- Result: PASS
- Test result: `41 passed`

**Status: PASS**

---

## 3. Stage 14.5 — Fail-Closed Session Secret Assurance

Production-readiness behavior was changed so that the runtime requires an explicitly configured `NS_SESSION_SECRET`.

Required behavior:

```python
SESSION_SECRET=(os.environ.get('NS_SESSION_SECRET') or '').strip()
if not SESSION_SECRET:
    raise RuntimeError('NS_SESSION_SECRET is required')
```

The previous silent ephemeral-secret fallback is not used on the Stage 14 production-readiness branch.

### CI assurance sequence

- Run #40 — FAILED
  - Exposed test-environment dependency after fail-closed enforcement.

- Run #41 — FAILED
  - Workflow YAML syntax/indentation defect identified.

- Run #42 — FAILED
  - Workflow executed successfully.
  - Exposed incorrect `DB_PATH` indentation.
  - Failure: `NameError: name 'DB_PATH' is not defined`

- Run #43 — GREEN
  - Corrected `DB_PATH` indentation.
  - Fail-closed session-secret control retained.

CI uses only a synthetic test value:

`stage14-ci-test-session-secret`

The Railway runtime secret was not copied into the workflow.

**Status: PASS**

---

## 4. Stage 14.6 — Persistent Runtime / Database Assurance

Railway service:

`north-star-uat-r3`

Persistent volume:

`north-star-uat-r3-volume`

Volume mount:

`/data`

Runtime database configuration:

`NS_DB_PATH=/data/runtime.sqlite3`

This establishes the configured persistence chain:

```text
north-star-uat-r3
        ↓
NS_DB_PATH=/data/runtime.sqlite3
        ↓
/data
        ↓
north-star-uat-r3-volume
```

A controlled Railway redeployment was performed.

### Before redeployment

- Microsoft Entra identity authenticated.
- Server-verified entitlement active.
- Access status: `Access enabled`.

### After redeployment

- Deployment successful.
- Same UAT identity authenticated.
- Existing entitlement remained active.
- Access status remained `Access enabled`.
- No new PayPal DEV transaction or entitlement grant was required.

This demonstrated persistence of the server-side entitlement state across redeployment.

**Status: PASS**

---

## 5. Stage 14.7 — Restart / Recovery Assurance

The controlled redeployment produced the expected startup sequence:

```text
Mounting volume
Starting Container
Started server process
Waiting for application startup
Application startup complete
Uvicorn running on 0.0.0.0:8080
GET /api/health → HTTP 200
```

The application recovered successfully with:

- persistent volume mounted;
- required runtime configuration accepted;
- application startup completed;
- health endpoint operational;
- persisted entitlement available.

Ask North Star was then tested after recovery.

Observed result:

`GROUNDED_EXPLANATION · GROQ`

The response remained governed by R4/B1 evidence and generated wording remained explicitly non-canonical.

**Status: PASS**

---

## 6. Stage 14.8 — Final Security and Configuration Verification

### 6.1 Runtime configuration

Required runtime variables were present, including:

- `NS_DB_PATH`
- `NS_LLM_MODE`
- `NS_LLM_MODEL`
- `NS_LLM_PROVIDER`
- `NS_LLM_TIMEOUT_SECONDS`
- `NS_SESSION_SECRET`

Secret values were not recorded in this evidence file.

### 6.2 Commerce / production boundary

Live UAT `/api/commerce/plans` verification confirmed:

```text
provider_first = PayPal
provider_runtime = PAYPAL_SIMULATOR
production_authorized = false
```

The UAT environment therefore remains outside production commerce authorization.

### 6.3 Unauthenticated AI boundary

An InPrivate unauthenticated session submitted an Ask North Star request.

The UI did not accept or return a generated answer.

Railway server evidence confirmed:

```text
POST /api/ai/ask → 401 Unauthorized
```

### 6.4 Authenticated AI boundary

An authenticated and entitled request to the same endpoint returned:

```text
POST /api/ai/ask → 200 OK
```

This confirms that the same endpoint remains protected according to identity and entitlement state.

### 6.5 Session-secret repository assurance

The controlled Stage 14 branch contains fail-closed session-secret behavior.

The contract CI workflow contains only the synthetic value:

`stage14-ci-test-session-secret`

The Railway `NS_SESSION_SECRET` value is maintained outside the repository and is not recorded in this evidence file.

**Status: PASS**

---

## 7. Stage 14.9 — Final Integrated Production-Readiness Regression

The final regression was executed without changing code, runtime variables, persistence configuration, entitlement state, or deployment configuration.

### Pre-test state

- Microsoft Entra External ID: Signed in.
- Managed server-side session: operational.
- Server-verified entitlement: `Access enabled`.
- `production_authorized=false`.

One controlled Ask North Star request was submitted:

> What are the key principles an executive should consider when governing enterprise technology transformation?

Observed application result:

`GROUNDED_EXPLANATION · GROQ`

The UI retained the governance boundary:

- provider execution is runtime-controlled;
- response is grounded in governed R4/B1 evidence;
- generated wording is not canonical North Star content.

Railway server evidence for the final transaction:

```text
2026-09-25 14:45:08 GMT+4
POST /api/ai/ask HTTP/1.1 → 200 OK
```

The final integrated authority chain was therefore demonstrated:

```text
Microsoft Entra External ID
        ↓
Managed server-side session
        ↓
Persisted server-side entitlement
        ↓
Premium AI authorization
        ↓
/api/ai/ask
        ↓
Governed R4/B1 evidence retrieval
        ↓
Provider-neutral external LLM adapter
        ↓
Groq transport
        ↓
Grounded, non-canonical explanation
        ↓
HTTP 200
```

**Status: PASS**

---

## 8. Final Stage 14 Control Register

| Control | Status |
|---|---|
| Stage 14 branch established | PASS |
| Stage 14.1 CI baseline | PASS |
| Stage 14.5 fail-closed session secret | PASS |
| Stage 14.5 contract CI | PASS |
| Stage 14.6 persistent runtime/database | PASS |
| Stage 14.6 redeployment persistence | PASS |
| Stage 14.7 startup/recovery | PASS |
| Stage 14.7 post-recovery AI execution | PASS |
| Stage 14.8 runtime configuration | PASS |
| Stage 14.8 commerce/production boundary | PASS |
| Stage 14.8 unauthenticated AI boundary | PASS |
| Stage 14.8 server-side authorization verification | PASS |
| Stage 14.8 session-secret assurance | PASS |
| Stage 14.9 final integrated regression | PASS |
| Outstanding Stage 14 HOLD | NONE |

---

## 9. Production Authorization Boundary

Stage 14 production readiness does not itself authorize production commerce or convert the UAT environment into a production environment.

At closure:

```text
production_authorized=false
provider_runtime=PAYPAL_SIMULATOR
```

These remain intentional controls.

Any future production authorization must be handled as a separate, explicitly governed release decision.

---

## 10. Security and Secret Handling

No production or UAT secret value is intentionally recorded in this closure evidence.

The following remain externally managed runtime configuration:

- Microsoft Entra client secret;
- Groq API key;
- North Star session secret.

Synthetic CI-only values are permitted for controlled automated testing and do not represent runtime production credentials.

---

## 11. Evidence Summary

Stage 14 demonstrated the following controlled operating state:

```text
Identity
  Microsoft Entra External ID
        ↓
Session
  Server-side / revocation-aware
        ↓
Authorization
  Server-verified entitlement
        ↓
Persistence
  /data/runtime.sqlite3
        ↓
Protected AI
  Premium AI authorization
        ↓
Governed Evidence
  R4/B1 retrieval boundary
        ↓
External Synthesis
  Provider-neutral adapter → Groq
        ↓
Governance Boundary
  Grounded explanation / non-canonical wording
```

The UAT environment additionally demonstrated:

```text
Unauthenticated AI request → 401 Unauthorized
Authenticated + entitled AI request → 200 OK
```

and:

```text
Controlled redeployment
        ↓
Persistent volume mounted
        ↓
Application startup complete
        ↓
Health endpoint 200
        ↓
Existing entitlement preserved
        ↓
Governed Groq execution successful
```

---

## 12. Closure Decision

All Stage 14 production-readiness controls exercised under this stage have produced satisfactory evidence.

No unresolved Stage 14 HOLD remains.

No security, authentication, entitlement, persistence, governed-AI, or production-authorization control was knowingly weakened to obtain closure.

# STAGE 14 — PRODUCTION READINESS: PASS / CLOSED

**Closure date:** 25 September 2026  
**Branch:** `stage-14-production-readiness`  
**Evidence principle:** Evidence before PASS.
