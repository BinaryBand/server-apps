# Contributing

Bounded constraints for contributors. The goal is a solution space tight enough that any output passing these rules is consistent, reviewable, and mergeable without negotiation.

See `ARCHITECTURE.md` for structural decisions and module ownership.

---

## Setup

```bash
poetry install
pre-commit install --hook-type pre-push
```

Open in VS Code from inside WSL (if on Windows):

```bash
code .
```

---

## Tooling Config

All tooling behavior is driven by committed config files — editor-agnostic, picked up automatically.

**`pyproject.toml`** — relevant sections:

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N"]

[tool.importlinter]
root_packages = ["src"]
```

**`.pre-commit-config.yaml`** — hooks run on push:

- `ruff` — lint with auto-fix
- `ruff-format` — format check
- `lizard` — complexity gates (CCN ≤ 5, length ≤ 25, params ≤ 4)
- `vulture` — dead code (min confidence 80)
- `lint-imports` — layer boundary contracts

**`pyrightconfig.json`** — per-project type checking rules.

---

## Rules

Every rule is paired with its enforcement tier.

| Rule | Tier | Mechanism |
| --- | --- | --- |
| Function length ≤ 25 lines | Automated | Lizard (pre-push) |
| Cyclomatic complexity ≤ 5 | Automated | Lizard (pre-push) |
| Parameters per function ≤ 4 | Automated | Lizard (pre-push) |
| No lint violations | Automated | Ruff (pre-push) |
| No dead code (≥ 80% confidence) | Automated | Vulture (pre-push) |
| Layer boundaries respected | Automated | import-linter (pre-push) |
| No type errors | Automated | Pyright (editor / CI) |
| Nesting depth ≤ 3 | Review | — |
| No mutable module-level globals | Review | — |
| No silent exception swallowing | Review | — |
| No vars, secrets, or paths outside Ansible | Review | — |
| No CQS violations — functions either mutate or return, not both | Review | — |

Prefer early returns over nested conditionals. If a function needs more than 25 lines, it has more than one responsibility — split it.

---

## Contribution Workflow

```text
0. After cloning:   poetry install && pre-commit install --hook-type pre-push
1. Branch from main
2. Run tests:       python -m pytest tests/unit -x
3. Run quality:     .venv/bin/ruff check src && .venv/bin/lint-imports
4. Push — pre-commit hooks run automatically
5. Open PR
```

### PR Checklist

- [ ] All automated checks pass
- [ ] Tests added or updated
- [ ] No secrets or paths hardcoded outside `src/infra/` or Ansible
- [ ] No CQS violations — functions either mutate or return, not both
- [ ] `ARCHITECTURE.md` updated if any structural decision changed
