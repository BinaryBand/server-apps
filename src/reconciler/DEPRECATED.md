# Deprecated reconciler

This package (`src.reconciler`) implements a reconciliation state-machine wrapper around the
canonical linear pipeline. The project's simplification plan prefers the linear pipeline as the
single orchestration model.

Planned actions:

- Operators: prefer the `src/orchestrators/reconcile.py` entrypoint which now runs the pipeline
  checkpoints directly and uses the runtime observer for `--check-only` probes.
- `src/reconciler` will be retired once tests and compatibility checks pass. Keep this directory
  until migration is complete and then remove it in a dedicated, reversible commit.

If you need a compatibility shim while migrating tests, call `src.reconciler.core.reconcile_once()`
but prefer the pipeline runner (`src.workflows.pipeline.PIPELINE_STEPS`) for new code.
