import os
import re
import shutil
import subprocess
import sys

import pytest


def _find_exec(name: str) -> str | None:
    path = shutil.which(name)
    if path:
        return path
    venv_bin = os.path.join(os.path.dirname(sys.executable), name)
    if os.path.exists(venv_bin):
        return venv_bin
    venv_bin_exe = venv_bin + (".exe" if os.name == "nt" else "")
    if os.path.exists(venv_bin_exe):
        return venv_bin_exe
    return None


def _run(cmd: list[str], env: dict | None = None, timeout: int = 300, check: bool = True):
    env = env or os.environ.copy()
    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        timeout=timeout,
    )
    if check and p.returncode != 0:
        pytest.fail(f"Command {cmd!r} failed (exit {p.returncode}):\n{p.stdout}")
    return p


def test_ruff_check():
    ruff = _find_exec("ruff")
    assert ruff, "ruff not found in PATH or venv"
    _run([ruff, "check", "src", "tests"])


def test_ruff_format_check():
    ruff = _find_exec("ruff")
    _run([ruff, "format", "--check", "src", "tests"])


def test_lizard_project():
    _run([sys.executable, "-m", "lizard", "src", "runbook", "-C", "5", "-L", "25", "-a", "4", "-w"])


def test_lizard_file_gate():
    _run(
        [
            sys.executable,
            "runbook/quality/lizard_file_gate.py",
            "src",
            "runbook",
            "--max-file-ccn-sum",
            "35",
            "--max-file-avg-ccn",
            "4.5",
            "--max-file-high-risk-funcs",
            "2",
            "--high-risk-ccn",
            "6",
        ]
    )


def test_vulture():
    _run([sys.executable, "-m", "vulture", "src", "runbook", "--min-confidence", "80"])


def test_import_linter():
    lint = _find_exec("lint-imports")
    assert lint, "lint-imports not found in PATH or venv"
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()
    _run([lint], env=env)


def test_semgrep_rules():
    semgrep = _find_exec("semgrep")
    if not semgrep:
        pytest.skip("semgrep not available in PATH or venv")
    _run([semgrep, "--config", "rules/semgrep/", "src", "--error"])


def test_ansible_lint():
    ansible_lint = _find_exec("ansible-lint")
    if not ansible_lint:
        pytest.skip("ansible-lint not available in PATH or venv")
    _run([ansible_lint, "ansible/"])


def test_jscpd_duplicates_fail_gate():
    """Run jscpd and fail the quality gate if any clones are detected."""
    jscpd = _find_exec("jscpd")
    npx = _find_exec("npx")
    if jscpd:
        p = subprocess.run(
            [jscpd, "--config", ".jscpd.json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=120,
        )
    elif npx:
        p = subprocess.run(
            [npx, "jscpd", "--config", ".jscpd.json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=120,
        )
    else:
        pytest.skip("jscpd / npx not available; skipping duplicate detection")

    out = p.stdout or ""
    # Look for `Found N clones.` line
    m = re.search(r"Found (\d+) clones?\.", out)
    if m:
        count = int(m.group(1))
        if count > 0:
            pytest.fail(f"jscpd detected {count} clones:\n{out}")
    else:
        # If output format differs, fail when jscpd exit code is non-zero
        if p.returncode != 0:
            pytest.fail(f"jscpd reported errors (exit {p.returncode}):\n{out}")
