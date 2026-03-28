# Plan: Close CS 701 Rubric Gaps for Full Marks

## Context

The CS 701 Presentation Rubric scores on **150 points** across 7 categories. 50 points are presentation-delivery items (preparation, speaking, posture, attire) that I can't help with code changes. The remaining **100 points** are technical deliverables where the codebase has clear gaps.

## Rubric Category Breakdown & Current Status

| Category | Points | Status | Gap |
|---|---|---|---|
| Preparation/Content Knowledge | 15 | N/A (delivery) | Practice & rehearsal |
| Speaking | 15 | N/A (delivery) | Delivery skill |
| Posture/Eye Contact | 10 | N/A (delivery) | Delivery skill |
| Attire | 10 | N/A (delivery) | Dress code |
| **PowerPoint Slides** | **20** | **MISSING** | No presentation exists |
| **Web/Software/App** | **20** | **Partial** | Bug list, testing results, error handling docs missing |
| **Database** | **20** | **Partial** | Backup/recovery plan missing |
| **Project Working Status** | **40** | **Partial** | System works but documentation gaps, needs polish |

## Gaps to Close (Technical — 100 pts)

### Gap 1: No PowerPoint Presentation (20 pts at risk)
**Rubric full-marks criteria:** No spelling errors, uniform slide colors, transitions, consistent fonts, 6x6 rule (max 6 bullets, 6 words each), non-distracting graphics.

**Action:** Cannot create a .pptx from code, but I can create a **presentation outline document** (`docs/PRESENTATION_OUTLINE.md`) with:
- Slide-by-slide content following the 6x6 rule
- Speaker notes for each slide
- Suggested visuals (screenshots, ERD, architecture diagram)
- Covers: project overview, architecture, database design, key features demo flow, testing strategy, challenges & resolutions

### Gap 2: No Bug List / Resolution Document (affects Web/Software 20 pts)
**Rubric full-marks criteria:** "Bug List/resolution, Testing results"

**Action:** Create `docs/BUG_LIST.md` — a formal bug tracking and resolution document:
- Extract real bugs from git history (`git log --grep="fix"`)
- Document: bug description, root cause, resolution, status
- Shows systematic debugging methodology

### Gap 3: No Testing Results Document (affects Web/Software 20 pts)
**Rubric full-marks criteria:** "Testing results"

**Action:** Create `docs/TESTING_RESULTS.md` — a formal test results report:
- Run `make test-backend` and `make test-frontend` to capture output
- Document: test counts, pass/fail rates, coverage percentages
- List what's tested (unit, integration, API routes, frontend components)
- Screenshot/output of test runs

### Gap 4: No Backup/Recovery Plan (affects Database 20 pts)
**Rubric full-marks criteria:** "contains backup recovery plan"

**Action:** Create `docs/BACKUP_RECOVERY.md`:
- PostgreSQL backup strategy (pg_dump, pg_basebackup)
- Recovery procedures (point-in-time recovery)
- Redis backup strategy (RDB snapshots)
- Retention policy
- Disaster recovery runbook

### Gap 5: Error Handling Not Documented (affects Web/Software 20 pts)
**Rubric full-marks criteria:** "error-handling routines"

**Action:** Create `docs/ERROR_HANDLING.md`:
- Document backend error handling patterns (custom exceptions, HTTP status codes, retry logic)
- Document frontend error handling (Axios interceptors, query error states, user-facing messages)
- Document external API error handling (Azure retry with Tenacity, LLM fallback chain)

### Gap 6: Code Documentation Sparse (affects Web/Software 20 pts)
**Rubric full-marks criteria:** "clearly written and well-documented code"

**Action:** Add docstrings to key service modules:
- `backend/app/services/ingestion.py` — main orchestration function
- `backend/app/services/anomaly.py` — detection algorithm
- `backend/app/services/recommendation.py` — LLM pipeline
- `backend/app/services/cost.py` — aggregation queries
- `backend/app/services/attribution.py` — allocation engine
- `backend/app/services/budget.py` — threshold checking
- `backend/app/services/notification.py` — delivery engine

### Gap 7: Screenshots Missing (affects Project Working Status 40 pts)
**Rubric full-marks criteria:** "System performs fully as designed; all documentation is consistent"

**Action:** The README says "Screenshots coming soon." We should capture screenshots of the running app and reference them. Since we can't easily take screenshots in this environment, update README to reference the live demo flow instead, or use Playwright MCP to capture screenshots.

## Execution Order

1. **Run tests** to capture current test results → `docs/TESTING_RESULTS.md`
2. **Extract bugs from git history** → `docs/BUG_LIST.md`
3. **Write backup/recovery plan** → `docs/BACKUP_RECOVERY.md`
4. **Write error handling documentation** → `docs/ERROR_HANDLING.md`
5. **Add docstrings** to 7 service modules (targeted, not excessive)
6. **Write presentation outline** → `docs/PRESENTATION_OUTLINE.md`
7. **Capture screenshots** of running app (if Docker is available)
8. **Update README** to remove "coming soon" and link new docs

## Files to Create
- `docs/PRESENTATION_OUTLINE.md`
- `docs/BUG_LIST.md`
- `docs/TESTING_RESULTS.md`
- `docs/BACKUP_RECOVERY.md`
- `docs/ERROR_HANDLING.md`

## Files to Modify
- `backend/app/services/ingestion.py` (add docstrings)
- `backend/app/services/anomaly.py` (add docstrings)
- `backend/app/services/recommendation.py` (add docstrings)
- `backend/app/services/cost.py` (add docstrings)
- `backend/app/services/attribution.py` (add docstrings)
- `backend/app/services/budget.py` (add docstrings)
- `backend/app/services/notification.py` (add docstrings)
- `README.md` (link new docs, update screenshots section)

## Verification
- All new docs are well-structured, consistent formatting, no spelling errors
- Docstrings follow Google-style Python docstring format
- Test results document shows actual test output
- Bug list shows real resolved bugs from git history
- `make test` still passes after docstring additions
