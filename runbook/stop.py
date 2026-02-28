import subprocess


if __name__ == "__main__":
    subprocess.run(["python", "-m", "src.shutdown"], check=True)
