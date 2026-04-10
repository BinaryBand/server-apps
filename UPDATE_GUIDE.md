# Simplification & Futureproofing Update Guide

This guide is a **handoff plan only** (no implementation applied here). It aligns with the latest `docs/UPDATED.md` (“Pipeline Design Playbook”) and translates it into a practical waterfall for this repository.

---

## 1) Final Architecture Decision

### Use one orchestration model: **Linear Pipeline only**

Adopt the updated playbook’s constraints directly:

- Forward-only flow
- One owner per concern
- Explicit enforcement
- Inward dependency direction
- Replaceable components

Given those constraints, keeping both:

1. a linear stage pipeline (`src/workflows/pipeline.py`), and
2. a separate reconciler/state-machine orchestration model (`src/reconciler/*`)

creates duplicate sequencing concepts and unnecessary cognitive load.

**Decision:** standardize on the linear pipeline model as the single runtime orchestration path.

---

## 2) How the latest `docs/UPDATED.md` changes affect the plan

The revised playbook strengthens and slightly adjusts direction in useful ways:

1. **Static pipeline declaration required**
   - “No runtime sequencing logic” in stage contracts reinforces removing reconciler-loop orchestration for normal runtime operations.

2. **Domain and pipeline may co-locate on small projects**
   - This supports reducing folder count without violating boundaries.
   - We can simplify structure while preserving logical separation.

3. **Context object is fixed at entry, enriched forward**
   - Encourages a single context shape and clear per-stage Reads/Writes docs.
   - Improves readability and onboarding.

4. **Cookie-cutter-first rule**
   - Supports removing bespoke wrappers/shims and duplicated abstractions where possible.

These updates **do not reverse** the previous simplification plan; they make it more concrete and easier to enforce.

---

## 3) Target Repository Shape (Simplified)

Keep structure minimal and readable while preserving ownership boundaries.

### Runtime Python

- Keep one clear execution path:
  - runbook entrypoints (`runbook/start.py`, `runbook/stop.py`, drop `runbook/reconcile.py`)
  - orchestrators (`src/orchestrators/*`)
  - single pipeline declaration (`src/workflows/pipeline.py`)
  - stage execution (`src/workflows/workflow_runner.py`)

- Remove duplicate orchestration domain:
  - retire `src/reconciler/` once compatibility and tests are migrated.

- Remove dual infra naming:
  - pick one canonical infrastructure namespace and remove the other compatibility layer/shims.
  - recommended canonical namespace: `src/infra`.

### Ansible

Current Ansible behavior is functionally rich but scattered across mixed top-level files + tasks + roles.

Simplify to:

- `ansible/playbooks/` as canonical entrypoints only
- role-owned logic under `ansible/roles/*`
- minimal top-level files for inventory/vars/manifests/requirements

---

## 4) Documentation Waterfall (must happen first)

Update docs in this strict order so all downstream docs derive from one source of truth.

1. **`docs/ARCHITECTURE.md`**
   - Merge in `docs/UPDATED.md` content as canonical guidance.
   - Replace placeholders with project-specific owners.
   - Include explicit pipeline declaration + stage contracts + contract matrix.
   - Remove stale migration warnings where no longer applicable.

2. **`README.md`**
   - Reflect single-model architecture (linear pipeline only).
   - Keep operational flow concise and human-readable.

3. **`docs/FLOW.md`**
   - Show one runtime flow path.
   - Remove obsolete references to toolbox migration and reconcile loop flow.

4. **`docs/REPO_STRUCTURE.md`**
   - Publish simplified tree and ownership boundaries.

5. **`docs/CONTRIBUTING.md`**
   - Align rules/enforcement with final boundaries and import-linter contracts.

6. **`docs/BACKUP_PIPELINE.md`**
   - Clean duplicated table rows and align wording with final architecture terms.

7. **`docs/COMPLEXITY.md`**
   - Update stale path references and current violation examples after namespace cleanup.

8. **`docs/UPDATED.md`**
   - Remove after merge to reduce doc duplication (or archive if explicit history is desired).

---

## 5) Code Refactor Waterfall (after docs)

### Phase A — Stabilize single pipeline path

1. Keep `PIPELINE_STEPS` as the only sequencing declaration.
2. Keep a single stage runner abstraction (`workflow_runner`) and remove duplicate sequencing paths.
3. Define one context/state contract for stage conditions used by orchestrators/checkpoints.

### Phase B — Retire reconciler model

1. Migrate command behavior currently in `src/reconciler/*` into linear pipeline compatible paths (if still needed).
2. Convert `runbook/reconcile.py` + `src/orchestrators/reconcile.py` into:
   - either a compatibility command that invokes linear checks/pipeline semantics, or
   - remove command if not required operationally.
3. Delete `src/reconciler/` once tests and docs pass.

### Phase C — Remove namespace duality (`toolbox` vs `infra`)

1. Replace imports from `src.toolbox.*` to canonical infra modules.
2. Remove shims/temporary compatibility modules once unused.
3. Update import-linter contracts to enforce final boundary explicitly.

### Phase D — Test and quality realignment

1. Update/retire reconciler-specific tests.
2. Keep behavior tests around stage order, failure behavior, idempotent stage reruns.
3. Ensure quality gates pass (`ruff`, `pytest`, `lint-imports`, `ansible-lint`).

---

## 6) Ansible Scaffolding Improvements (concrete)

### Goals

- Fewer entrypoints
- Role-owned behavior
- Clear runtime vs bootstrap/reset separation
- Better readability for humans

### Recommended changes

1. **Canonicalize playbook entrypoints**
   - Move top-level `ansible/apply-permissions.yml` into `ansible/playbooks/runtime.yml` (or similarly clear name).
   - Keep only playbooks under `ansible/playbooks/` as public command targets.

2. **Promote task file into role boundary**
   - Move `ansible/tasks/reconcile-startup.yml` into a dedicated role (example: `roles/runtime_stack/tasks/main.yml`).
   - Keep playbook thin; keep behavior in role tasks.

3. **Clean dead/low-value scaffolding**
   - Remove debug-only task(s) from runtime task flow.
   - Remove duplicate/unused template roots (if unused after migration).
   - Remove empty runtime scaffolding directories that are not source-controlled artifacts.

4. **Add operator-facing Ansible map**
   - Add `ansible/README.md` with:
     - command matrix (runtime/bootstrap/reset/ssh/systemd/provision),
     - required env vars,
     - which roles each playbook executes.

5. **Prefer module-driven tasks where possible**
   - Keep shell/command calls only where modules cannot express behavior.
   - Use named helper vars for repeated compose command fragments.

---

## 7) Migration Safeguards

1. **Compatibility-first CLI migration**
   - Preserve entrypoint scripts (`runbook/*.py`) while internals are simplified.

2. **Small, reversible commits by phase**
   - Docs first, then structural refactor, then cleanup.

3. **Contract checks before deletions**
   - Verify no remaining imports/tests reference removed modules before deletion.

4. **Operational parity checks**
   - Validate `start`, `stop`, permissions apply, and backup/restore paths remain functional.

---

## 8) Acceptance Criteria

The simplification is complete when all are true:

1. One orchestration model exists in code and docs (linear pipeline only).
2. No stale migration language remains in core docs.
3. No dual infra namespace/shim confusion remains.
4. Ansible has one obvious entrypoint pattern and role-owned behavior.
5. Tests + quality gates pass on the simplified structure.
6. New contributor can identify “where to change what” quickly from `README.md`, `docs/ARCHITECTURE.md`, and `docs/REPO_STRUCTURE.md`.

---

## 9) Suggested Execution Order (single checklist)

1. Merge `UPDATED.md` into `ARCHITECTURE.md`.
2. Cascade doc updates (`README`, `FLOW`, `REPO_STRUCTURE`, `CONTRIBUTING`, backup/complexity docs).
3. Lock single pipeline path and retire reconciler model.
4. Unify infra namespace and remove compatibility shims.
5. Reorganize Ansible entrypoints/tasks into cleaner role-centered scaffolding.
6. Update tests and pass all quality gates.
7. Delete `docs/UPDATED.md` (or archive explicitly).
