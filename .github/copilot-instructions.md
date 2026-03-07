# Copilot Instructions

## Purpose

These instructions are for practical, enforceable guidance in this repository.
Use this as the default review baseline for AI-authored and human-authored changes.

## Current Architecture (Enforceable)

- `runbook/*.py`: Orchestrators that sequence stages and parse CLI arguments.
- `ansible/apply-permissions.yml`: Manager-like reconciliation for host/runtime state.
- `src/backups/*`, `src/reset/*`, `src/project/*`, `src/utils/*`: Toolbox and helper modules.
- `compose/*.yml`, `infra/*.yml`, `configs/*`, `.env*`: Declarative configuration.

## Core Rules

### Separation Of Concerns

- Keep orchestration flow and stage ordering in `runbook/*`.
- Keep subprocess wrappers, file transforms, and integration helpers in `src/*`.
- Keep imperative workflow logic out of Compose and infra manifests.

### Single Responsibility

- If a module starts managing both stage sequencing and low-level command construction, split it.
- Keep environment/path/volume resolution centralized in `src/utils/runtime.py`, `src/utils/secrets.py`, and `src/utils/volumes.py`.

### Explicit Dependencies

- Prefer explicit function args for project names, target paths, and feature flags.
- Allow environment-driven defaults, but keep override points visible in runbook CLI args.
- For new storage-related logic, support named-volume defaults with optional host path overrides.

### Idempotency Strategy

Every changed operation must have one of these documented in code comments or PR notes:

1. Naturally idempotent behavior, or
2. Explicit idempotency marker/tag strategy, or
3. Intentional non-idempotent behavior with guardrails and a warning.

Repo-specific expectations:

- `ansible/apply-permissions.yml` tasks should remain declarative/idempotent.
- Backup and restore flows must clearly call out destructive operations, especially `rclone sync` apply steps.
- When changing snapshot behavior, document how `latest` and tags are expected to behave.

### Error Handling

- Toolbox modules should raise contextual exceptions with command/stage details.
- Orchestrators should catch errors at stage boundaries and emit actionable messages.
- Avoid returning raw subprocess errors without context about which stage failed.

### Observability

- Log stage boundaries in `runbook/*`.
- Log external command invocations in Toolbox modules before execution.
- Include enough context to troubleshoot path, mount, and volume resolution quickly.

## Target State (Do Not Block PRs Yet)

These are architectural goals that may require refactors:

- Move direct Ansible shell execution into a reusable toolbox wrapper.
- Tighten typed error hierarchy across backup/restore/reset modules.
- Reduce orchestration decision logic inside toolbox functions where practical.

When proposing these improvements, include migration steps and scope them separately from urgent fixes.

## Pull Request Review Checklist

- [ ] Is orchestration logic primarily confined to `runbook/*`?
- [ ] Are Compose/infra/config changes declarative rather than procedural?
- [ ] Is idempotency behavior clear for each modified operational path?
- [ ] Are failure messages stage-aware and actionable?
- [ ] Are storage path assumptions explicit and overrideable?
- [ ] Are target-state refactors separated from immediate bugfixes?
