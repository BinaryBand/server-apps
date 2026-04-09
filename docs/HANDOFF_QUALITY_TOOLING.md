# Handoff: Quality Tooling Expansion

## Current state

Already wired (pre-commit + VS Code tasks):

| Tool | Coverage | Config |
|---|---|---|
| Ruff `E/F/W/I/N` | Lint + format | `pyproject.toml` |
| Vulture (≥80% confidence) | Dead code | pre-commit |
| Lizard (CCN ≤5, length ≤25, params ≤4) | Function complexity | pre-commit |
| `scripts/quality/lizard_file_gate.py` | File-level complexity budget | VS Code task |
| import-linter (2 contracts) | Layer boundary enforcement | `pyproject.toml` |
| `scripts/quality/quality_watch.py` | Live background watcher | VS Code task (auto-start) |

No CI pipeline exists (no `.github/`). All checks are local/pre-push only.

---

## What to add

Three tiers, ordered by ROI. Do them in order — each is independent.

---

### Tier 1 — Expand Ruff (no new tools, pure config change)

**File: `pyproject.toml`**

Change `select`:
```toml
[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "A", "B", "S"]
```

Add `ignore` to suppress the noisy-but-not-real S violations:
```toml
ignore = [
    "S603",   # subprocess call without shell=True — all calls in this project use
              # hardcoded arg lists (docker, ansible-playbook, rclone). Not a real risk.
    "S607",   # start-process-with-partial-path — same rationale; "docker" is fine here.
]
```

Add test-file exemptions (S101 = assert, B011 = assert False):
```toml
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]
```

**What this adds:**

- `A` — catches builtins shadowing (`list`, `id`, `type`, etc.) — currently 0 violations, purely preventive
- `B` (bugbear) — Python antipatterns (mutable defaults, redundant open modes, etc.) — currently 0 violations
- `S` minus S603/S607 — remaining bandit rules: hardcoded passwords (S105/S106), bare `except: pass` (S110), temp file misuse (S108), `assert` in production code (S101), etc.

**Validate:** `ruff check src runbook` should exit 0 after config change.

---

### Tier 2 — Duplicate detection

Lizard has no duplicate detection. jscpd (the best cross-language option) requires npm, which this project doesn't currently use.

**Option A — jscpd via npm (recommended if npm is available on dev machine):**

Install globally or add to npm devDependencies:
```bash
npm install -g jscpd
```

Create `.jscpd.json` at project root:
```json
{
  "minLines": 8,
  "minTokens": 50,
  "languages": ["python"],
  "path": ["src", "runbook"],
  "reporters": ["console"],
  "ignore": ["**/.venv/**", "**/typings/**"]
}
```

Add to `.pre-commit-config.yaml` as a local hook:
```yaml
      - id: jscpd
        name: Duplicate code detection (jscpd)
        entry: jscpd
        language: system
        args: ["--config", ".jscpd.json"]
        pass_filenames: false
```

**Option B — defer:** For a single-dev Python project, Ruff + Vulture + code review is sufficient coverage. Duplicate detection catches structural drift that's hard to spot in review; add it when the codebase grows or when AI-generated code volume increases.

**Recommendation:** Add Option A if npm is already on the machine. Otherwise defer.

---

### Tier 3 — Semgrep custom rules

Import-linter enforces package-level boundary contracts. Semgrep can enforce *within-file* patterns that import-linter can't catch — specifically subprocess hygiene and direct infrastructure calls from the wrong layer.

**Install:**
```bash
poetry add --group dev semgrep
```

**Create `rules/semgrep/no-os-system.yml`:**
```yaml
rules:
  - id: no-os-system
    pattern: os.system(...)
    message: "Use subprocess.run() instead of os.system() — no shell injection surface."
    languages: [python]
    severity: ERROR
```

**Create `rules/semgrep/no-shell-true.yml`:**
```yaml
rules:
  - id: no-subprocess-shell-true
    pattern: subprocess.run(..., shell=True, ...)
    message: "subprocess.run with shell=True is forbidden — construct arg lists instead."
    languages: [python]
    severity: ERROR
```

Add to `.pre-commit-config.yaml`:
```yaml
      - id: semgrep
        name: Semgrep custom rules
        entry: semgrep
        language: system
        args: ["--config", "rules/semgrep/", "src/", "--error"]
        pass_filenames: false
```

**Note:** These two rules have 0 current violations — this is preventive. Expand the ruleset as patterns emerge from AI-generated code.

---

### Skip (not worth the overhead for this project)

| Tool | Why skip |
|---|---|
| NiCad | Java-based, complex setup, Python-only project — jscpd covers duplicate detection better |
| CodeQL | Needs a CI pipeline first; add after `.github/workflows/` is set up |
| Mutation testing (`mutmut`) | High run time, low ROI for infrastructure automation code with mostly integration-style tests |
| Ruff `C90` (McCabe) | Redundant — Lizard already enforces CCN; having two tools for the same metric adds noise |

---

## Execution order

1. **Expand Ruff** — `pyproject.toml` only, 5-minute change, verify with `ruff check src`
2. **jscpd** (if npm available) — `.jscpd.json` + pre-commit hook
3. **Semgrep rules** — `rules/semgrep/` + install + pre-commit hook

Steps 2 and 3 are independent and can be done in either order.

---

## Post-expansion gate sequence

Once all tiers are complete, the full pre-push gate will be:

```
ruff check         → lint (E/F/W/I/N/A/B/S)
ruff format        → format check
lizard             → function complexity (CCN ≤5, length ≤25, params ≤4)
vulture            → dead code (≥80%)
import-linter      → layer boundary contracts
jscpd              → duplicate detection (≥8 lines / ≥50 tokens)
semgrep            → custom structural rules (os.system, shell=True)
```

VS Code tasks cover the first five interactively. Add jscpd and semgrep as VS Code tasks to match once the hooks are in place.
