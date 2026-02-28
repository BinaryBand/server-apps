import subprocess

# python -m src.backups.backup --src "C:\Users\ShaneD\Documents\Development\docker\cloud-apps\jellyfin\data\data\jellyfin.db"

if __name__ == "__main__":
    # subprocess.run(["python", "-m", "src.reset.reset_storage"], check=True)

    # volume = "jelly_data"
    # subprocess.run(
    #     ["python", "-m", "src.backups.snapshot", "--volume", volume], check=True
    # )

    # python -m src.backups.restore --src "C:\path\to\jellyfin.db" --stop --start
    db_path = "C:/Users/ShaneD/Documents/Development/docker/cloud-apps/jellyfin/data/data/jellyfin.db"
    subprocess.run(
        ["python", "-m", "src.backups.restore", "--src", db_path, "--stop", "--start"],
        check=True,
    )

    # src = "C:/Users/ShaneD/Documents/Development/docker/cloud-apps/jellyfin/data/data/jellyfin.db"
    # subprocess.run(["python", "-m", "src.backups.backup", "--src", src], check=True)
