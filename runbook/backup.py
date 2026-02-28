from dotenv import load_dotenv
import subprocess
import os


def main():
    load_dotenv()

    project_name = os.getenv("PROJECT_NAME", "cloud")

    jellyfin_config_volume = f"{project_name}_jellyfin_config"
    jellyfin_config_dest = ".local/backups/jellyfin_config"

    jellyfin_data_volume = f"{project_name}_jellyfin_data"
    jellyfin_data_dest = ".local/backups/jellyfin_data"

    subprocess.run(
        [
            "python",
            "-m",
            "src.backups.snapshot",
            "--volume",
            jellyfin_config_volume,
            "--output",
            jellyfin_config_dest,
        ],
        check=True,
    )
    subprocess.run(
        [
            "python",
            "-m",
            "src.backups.snapshot",
            "--volume",
            jellyfin_data_volume,
            "--output",
            jellyfin_data_dest,
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
