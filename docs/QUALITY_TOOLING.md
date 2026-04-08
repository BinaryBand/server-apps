# Quality Tooling Draft

This document captures a practical quality stack for assisted (teams/AI/etc...) development.

## Goals

- Detect dead code and complexity drift early.
- Catch duplicate and near-duplicate logic before it spreads.
- Enforce architecture boundaries and security rules.
- Keep checks portable across future language stacks.

## Current Core Candidates

### 1) Vulture (Python)

- Purpose: dead code and unused symbol detection.
- Strength: simple, fast, useful for cleanup gates.
- Scope: Python only.

### 2) Lizard (Multi-language)

- Purpose: function complexity and length thresholds.
- Strength: broad language coverage, low setup friction.
- Scope: complexity metrics, not clone detection.

### 3) NiCad (Clone detection)

- Purpose: near-miss clone detection (more than exact text duplicates).
- Strength: strong duplicate/near-duplicate analysis.
- Scope: supports multiple languages overall, usually analyzed one language per run.

## Recommended Additions

### 4) Semgrep (Cross-language)

- Purpose: structural/static rules for security and architecture.
- Why add: excellent for multi-member team guardrails (forbidden APIs, unsafe patterns, layering violations).

### 5) CodeQL (Cross-language)

- Purpose: deeper security and dataflow analysis.
- Why add: finds classes of issues basic linting misses.

### 6) jscpd or PMD CPD (Cross-language duplication)

- Purpose: token/text-level duplicate detection across many languages.
- Why add: fast signal for repeated large blocks in polyglot repos.

### 7) import-linter (Python architecture contracts)

- Purpose: enforce import boundaries between modules/packages.
- Why add: strong anti-drift control.

### 8) Mutation testing (optional, high value)

- Tools: mutmut or cosmic-ray (Python).
- Purpose: test quality strength, not style.
- Why add: detects weak tests that allow subtle regressions.

## Baseline Stack by Priority

### Tier 1 (fast, high ROI)

- Ruff (lint + format)
- Vulture
- Lizard
- jscpd

### Tier 2 (guardrails)

- Semgrep
- import-linter

### Tier 3 (deep analysis)

- NiCad
- CodeQL
- Mutation testing

## Starter Pipeline Template

Use this as a rough CI/local gate sequence:

1. Format and lint
2. Dead code scan
3. Complexity gates
4. Duplicate/near-duplicate scan
5. Security/architecture rule checks
6. Tests and optional mutation tests

## Example Gate Mapping (Python-first)

- Format/lint: Ruff
- Dead code: Vulture
- Complexity: Lizard + file-level gate script
- Duplicates: jscpd (always) + NiCad (scheduled/deeper pass)
- Architecture rules: import-linter + Semgrep custom rules
- Security deep scan: CodeQL in CI

## Cross-Language Portability Notes

- Keep Semgrep and jscpd in every stack where possible.
- Use Lizard for complexity as a common baseline across languages.
- Use language-specific architecture tools where import-linter equivalents exist.
- Keep NiCad as a deeper clone audit layer when duplicate risk is high.

## AI Corralling Practices

- Fail fast on boundary violations (architecture/security rules).
- Keep thresholds explicit and versioned in repo config.
- Prefer deterministic checks in PRs; run heavier checks nightly.
- Treat repeated findings as refactor candidates, not just warnings.

## Suggested First Implementation Pass for This Repo

1. Keep existing Ruff + Vulture + Lizard gates.
2. Add jscpd for broad duplicate detection.
3. Add Semgrep with a minimal custom ruleset.
4. Add import-linter contract checks for package boundaries.
5. Add CodeQL in CI once rule noise is tuned.
