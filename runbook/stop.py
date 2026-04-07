import sys

from runbook._launcher import run_orchestrator

if __name__ == "__main__":
    sys.exit(run_orchestrator("stop"))
