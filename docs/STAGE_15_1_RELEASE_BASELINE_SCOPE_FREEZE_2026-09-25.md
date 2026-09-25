# NORTH STAR — Stage 15.1 Release Baseline & Scope Freeze

**Project:** NORTH STAR — The Executive Guide to Enterprise Technology, Leadership & Transformation  
**Stage:** 15 — Release & Publication Lock  
**Sub-stage:** 15.1 — Release Baseline & Scope Freeze  
**Branch:** `stage-15-release-publication-lock`  
**Baseline Date:** 25 September 2026  
**Status:** BASELINE / SCOPE FREEZE CANDIDATE  

---

## 1. Purpose

Stage 15.1 establishes the controlled release baseline for North Star before final publication-lock activities begin.

The purpose of this control is to:

- identify the authoritative release components;
- distinguish publication-master assets from digital-platform assets;
- preserve previously approved and closed work;
- identify the remaining release dependencies;
- prevent unnecessary reopening of completed engineering or editorial work; and
- establish the controlled starting point for Stage 15.

The governing principle remains:

> Evidence before PASS.

Stage 15 is a release-control phase. It is not a new development or editorial cycle.

---

## 2. Stage 15 Entry Condition

Stage 15 begins from the controlled completion of:

`Stage 14 — Production Readiness: PASS / CLOSED`

Stage 14 closure date:

`25 September 2026`

The Stage 15 branch was created directly from:

`stage-14-production-readiness`

New controlled branch:

`stage-15-release-publication-lock`

This preserves the verified Stage 14 technical baseline while isolating Stage 15 release and publication-lock activities.

---

## 3. Release-Control Model

North Star maintains two related but distinct control domains.

### 3.1 Publication Master Control

The publication-master domain contains the authoritative canonical publication assets, including:

- approved R4 publication content;
- approved final graphics;
- authoritative wraparound cover artwork;
- approved digital/e-version assets;
- publication metadata;
- ISBN / publisher / imprint information; and
- final publication assurance evidence.

These assets are not duplicated into the digital-platform repository merely to satisfy Stage 15 controls.

### 3.2 Digital Platform Control

The GitHub repository controls the digital application and governed retrieval implementation.

The Stage 15 branch inherits the controlled technical structure including:

```text
.github/workflows/
app/
data/
docs/
tests/
Procfile
Procfile.entra-uat
requirements.txt
```

The repository therefore controls application/runtime implementation and technical assurance evidence rather than serving as the authoritative storage location for all publication masters.

---

## 4. Authoritative Publication Baseline

The following publication components enter Stage 15 with their existing approved state preserved.

| Component | Entry State | Stage 15 Control |
|---|---|---|
| R4 publication content | LOCKED / APPROVED | Preserve; no uncontrolled editorial reopening |
| Final Publication Assurance R1 | APPROVED | Preserve |
| H1 Executive Quote / Provenance Assurance | PASS / CLOSED | Preserve |
| 28 final graphics | APPROVED | Preserve; no redesign |
| North Star Compass™ and approved visual system | APPROVED | Preserve |
| Authoritative wraparound cover | APPROVED MASTER | Preserve; adapt only to required final production template where necessary |
| E-version E1 | APPROVED | Preserve |
| E-version E2 | APPROVED | Preserve |
| E-version E3 | APPROVED | Preserve |
| E4 owner UAT | COMPLETED | Preserve evidence |
| ISBN / NLA treatment | PENDING RELEASE DEPENDENCY | Resolve under Stage 15.2 |
| Publisher / imprint metadata | PENDING FINAL LOCK | Resolve under Stage 15.2 |

No item classified as LOCKED, APPROVED, PASS / CLOSED, or COMPLETED is reopened merely because Stage 15 has begun.

---

## 5. Digital Platform Baseline

The Stage 15 branch inherits the verified Stage 14 technical baseline.

### Controlled repository areas

```text
.github/workflows/
app/
data/
docs/
tests/
Procfile
Procfile.entra-uat
```

The repository includes controlled implementation and assurance for:

- Microsoft Entra External ID integration;
- server-side managed sessions;
- server-side entitlement authority;
- persistent runtime/database configuration;
- governed retrieval evidence;
- provider-neutral external LLM integration;
- Groq transport;
- protected Ask North Star execution;
- observability and UAT controls;
- PayPal-first commerce architecture;
- CI contract testing; and
- production-readiness assurance.

### Stage status inherited into Stage 15

| Technical Stage | State |
|---|---|
| Stage 11 — Portal / entitlement controls | COMPLETED |
| Stage 12 — External LLM R2 Readiness | PASS / CLOSED |
| Stage 13 — External LLM Operational Assurance | COMPLETED |
| Stage 14 — Production Readiness | PASS / CLOSED |

These technical stages constitute the frozen Stage 15 entry baseline.

---

## 6. Stage 14 Technical Freeze

Stage 14 is frozen following evidence-backed closure.

The following controls must not be changed during publication-lock work unless a genuine defect or formally approved release requirement requires controlled reopening:

- authentication behavior;
- session-secret enforcement;
- server-side entitlement behavior;
- persistent database configuration;
- Railway volume configuration;
- governed retrieval boundary;
- external LLM provider-neutral adapter;
- Groq transport;
- AI authorization boundary;
- canonical/non-canonical content boundary;
- commerce authorization boundary; and
- production authorization state.

Any required reopening must be explicitly documented rather than silently incorporated into publication work.

---

## 7. Governed AI Boundary

Ask North Star remains governed by the established R4/B1 evidence boundary.

The operating model remains:

```text
Governed R4/B1 evidence
        ↓
Retrieval
        ↓
Provider-neutral external LLM adapter
        ↓
External synthesis
        ↓
Grounded explanation
```

Generated wording is not canonical North Star publication content.

The assistant may explain, navigate, compare, and support decisions using governed evidence, but it must not silently rewrite the approved publication master or present generated wording as canonical North Star content.

This boundary remains frozen during Stage 15.

---

## 8. Identity and Entitlement Baseline

The verified Stage 14 operating chain remains:

```text
Microsoft Entra External ID
        ↓
Managed server-side session
        ↓
Server-verified entitlement
        ↓
Protected North Star capability
```

Final Stage 14 integrated verification demonstrated:

```text
Unauthenticated protected AI request
        ↓
401 Unauthorized
```

and:

```text
Authenticated + entitled AI request
        ↓
200 OK
```

No Stage 15 publication activity requires weakening this boundary.

---

## 9. Persistence Baseline

The controlled UAT persistence configuration entering Stage 15 is:

```text
NS_DB_PATH=/data/runtime.sqlite3
```

with the Railway volume mounted at:

```text
/data
```

Stage 14 verified that entitlement state persisted across controlled redeployment.

This configuration is frozen unless a separately governed technical requirement requires modification.

---

## 10. Production Authorization Boundary

Stage 15 release/publication lock does not automatically authorize production commerce or convert the UAT environment into a production commerce environment.

The Stage 14 verified boundary remains:

```text
provider_runtime=PAYPAL_SIMULATOR
production_authorized=false
```

This state must be preserved throughout publication lock unless production authorization is separately reviewed, evidenced, and explicitly approved.

Publication readiness and production-commerce authorization are separate decisions.

---

## 11. Stage 15 Scope

The controlled Stage 15 scope is:

### 15.1 — Release Baseline & Scope Freeze

Establish and freeze the authoritative release baseline.

### 15.2 — ISBN / Publisher / Imprint Metadata Lock

Resolve the remaining ISBN, publisher, imprint, and publication-metadata dependencies.

### 15.3 — Publication Asset Integrity Assurance

Verify that the final manuscript, graphics, cover, navigation, front/back matter, and related publication assets correspond to the approved baseline.

### 15.4 — Digital Release Candidate Assembly

Assemble and verify the controlled digital publication release candidate using already-approved content and corrections.

### 15.5 — Portal + Publication Release Alignment

Confirm alignment between the canonical publication release and the portal's governed R4/B1 evidence boundary without reopening completed Stage 14 engineering.

### 15.6 — Final Release Assurance & Publication Lock

Perform the final release assurance, resolve any explicit HOLD, and establish the final Publication Lock / Release Candidate state.

---

## 12. Explicitly Out of Scope for Stage 15.1

The following are not authorized by this baseline-control step:

- new manuscript rewriting;
- redesign of the approved cover;
- redesign of approved graphics;
- arbitrary portal feature development;
- authentication redesign;
- entitlement redesign;
- persistence redesign;
- external LLM architecture redesign;
- provider migration;
- production commerce activation;
- changing `production_authorized` to `true`;
- replacing the approved publication master;
- silently correcting canonical content; or
- merging Stage 15 into `main`.

Any newly discovered defect must be recorded and assessed before modifying a frozen component.

---

## 13. Release Baseline Classification

### LOCKED / APPROVED

- R4 publication content
- Final Publication Assurance R1
- H1 Executive Quote / Provenance Assurance
- 28 final graphics
- North Star Compass™ / approved visual system
- authoritative wraparound cover
- approved E-version baseline
- Stage 11 completed portal baseline
- Stage 12 closed external-LLM baseline
- Stage 13 operational-assurance baseline
- Stage 14 production-readiness baseline

### READY / FROZEN

- Stage 15 GitHub technical baseline
- governed retrieval implementation
- Microsoft Entra identity boundary
- server-side entitlement authority
- persistent runtime configuration
- external LLM adapter and Groq transport
- protected Ask North Star execution
- CI and assurance controls

### PENDING

- ISBN / NLA final treatment
- publisher / imprint metadata lock
- final publication metadata reconciliation
- Stage 15.3 publication asset integrity verification
- Stage 15.4 release candidate assembly
- Stage 15.5 portal/publication alignment
- Stage 15.6 final release assurance

### NOT AUTHORIZED BY THIS STAGE

- production commerce activation
- uncontrolled production launch
- canonical content rewriting
- Stage 14 engineering reopening without documented cause

---

## 14. Controlled Release Path

The Stage 15 release path is:

```text
Approved R4 Publication Master
        +
Approved Graphics
        +
Authoritative Cover Master
        +
Approved Digital Edition Baseline
        +
ISBN / Publisher / Imprint Metadata
        +
Frozen Stage 14 Technical Baseline
        ↓
Publication Asset Integrity Assurance
        ↓
Digital Release Candidate
        ↓
Portal / Publication Alignment
        ↓
Final Release Assurance
        ↓
NORTH STAR
PUBLICATION LOCK / RELEASE CANDIDATE
```

---

## 15. Change-Control Rule

From this baseline forward:

> A frozen component is not modified merely because an improvement is possible.

A change requires an identified release requirement, defect, compliance need, publication dependency, or other documented justification.

Where a change is necessary:

1. identify the affected frozen component;
2. record the reason;
3. assess the release impact;
4. make the narrowest necessary correction;
5. execute the applicable assurance;
6. preserve evidence; and
7. only then update the release baseline.

This prevents Stage 15 from becoming an uncontrolled development cycle.

---

## 16. Stage 15.1 Exit Criteria

Stage 15.1 may be declared PASS / CLOSED when:

- the Stage 15 branch lineage is confirmed;
- publication and platform control domains are distinguished;
- approved and frozen assets are identified;
- pending release dependencies are identified;
- the Stage 14 technical baseline remains frozen;
- production authorization remains unchanged;
- Stage 15 scope is explicitly defined;
- out-of-scope activities are explicitly defined; and
- this baseline evidence is committed to the controlled Stage 15 branch.

At the time this document is prepared, no identified condition requires reopening Stage 14.

---

## 17. Baseline Decision

The North Star release baseline is sufficiently defined to begin controlled publication-lock activities.

Previously approved publication assets remain authoritative.

Previously closed technical controls remain frozen.

The principal remaining publication dependency entering the next control is ISBN / publisher / imprint metadata finalization.

No production-commerce authorization is granted by this baseline.

# STAGE 15.1 — RELEASE BASELINE & SCOPE FREEZE: PASS CANDIDATE

**Baseline date:** 25 September 2026  
**Branch:** `stage-15-release-publication-lock`  
**Next control:** Stage 15.2 — ISBN / Publisher / Imprint Metadata Lock  
**Evidence principle:** Evidence before PASS.
