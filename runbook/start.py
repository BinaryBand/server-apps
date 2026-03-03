import subprocess
import sys


if __name__ == "__main__":
    subprocess.run([sys.executable, "-m", "src.project.init"], check=True)
