# Copilot Instructions

## [Architectural Checklist](https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/architectural-principles)

- [ ] Separation of Concerns
- [ ] Encapsulation
- [ ] Dependency Inversion
- [ ] Explicit Dependencies
- [ ] Single Responsibility
- [ ] Don't Repeat Yourself (DRY)
- [ ] Persistence-agnostic
- [ ] Bounded Contexts
- [ ] Idempotency
- [ ] Observability

## Separation of Concerns

An individual component must be exactly one of: Orchestrator, Manager, Toolbox, or Configuration.

- **Orchestrator**
  - Role: Linear pipeline runner — funnels data through a fixed sequence of Toolbox calls and Manager handoffs.
  - Lifecycle: Ephemeral per-request/goal.
  - Responsibilities: compose task list, enforce per-stage deadlines/cancellation, implement retries/backoff for orchestration-level failures, emit structured telemetry.
- **Manager**
  - Role: Stateful router/reconciler — observes the domain state in its scope, routes data to functions/managers, updates desired state, and returns data to the Orchestrator when ready for the next pipeline stage.
  - Lifecycle: Long-lived, event-driven, reconciler loop.
  - Responsibilities: routing, backpressure, rate-limiting, remediation decisions, event emission.
- **Toolbox**
  - Role: Pure processors — transform input → output, no control flow or orchestration responsibilities.
  - Lifecycle: Stateless, callable functions/services.
  - Responsibilities: deterministic processing, typed I/O, return structured errors; must NOT implement retries/timeouts/backoff (cooperative cancellation hooks are allowed); idempotency or idempotency keys required.
- **Configuration**
  - Role: Declarative data artifacts (service definitions, inventories, variables).
  - Properties: immutable, canonical, validated, versioned, and human-diffable; may be transformed/packed at build/deploy time.
  - Must not contain imperative orchestration logic.

## Single responsibility

If a component is doing multiple things, split it into multiple components.

- **Python**
  - Role: implement either Orchestrators or Toolbox functions (never both in same component/module). Utilities (logging, tracing helpers, schema validators) must be non-orchestrating.
  - Orchestrator scripts: accept handoff messages, call toolboxes/managers, enforce per-stage deadlines, and emit structured events/telemetry.
  - Toolbox functions: pure behavior, deterministic errors, typed I/O, idempotency keys. No internal retries/timeouts/backoff.

## No shell in Python

- Do not execute shell snippets from Python (no `sh -lc`, `/bin/sh -c`, `bash -c`, or command strings with `&&`, `||`, pipes, redirects, or globs).
- Build commands as explicit argv lists and run them with `subprocess.run([...], check=...)`.
- Separate command construction from execution: use small command-builder helpers that return `list[str]`, and thin executor functions that run those lists.
- Prefer native APIs over shell utilities when available (`Path`, `os`, `shutil`, Docker/SDK wrappers, Ansible modules).
- If no non-shell equivalent exists, document the exception at the call site and keep it isolated behind a single helper.
- **Ansible**
  - Treat playbooks/roles as declarative, idempotent configuration applicators (configuration/manager-like for infra state). Keep roles small and single-purpose.
  - Avoid embedding orchestration sequencing; if ordered execution is required, have an Orchestrator (Python) invoke playbooks as distinct steps.
  - Use inventories/vars as versioned configuration artifacts and validate them in CI (molecule or equivalent).
- **Docker Compose**
  - Treat compose files as human-diffable configuration describing service wiring and runtime hints only.
  - Avoid embedding runtime orchestration (complex startup sequencing, retries). Use Orchestrator-managed startup sequencing or a lightweight init container when necessary.
  - Prefer healthchecks, restart policies, and network definitions rather than procedural logic.
