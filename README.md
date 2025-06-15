# Navidrome Top Tracks Updater

This script updates the play count statistics of your Navidrome server to ensure that an artist's "Top Tracks" section reflects their actual popular hits, based on data from Last.fm.

## Prerequisites

- Python 3.8+ (on the host machine)
- A working Navidrome installation running in Docker
- An API Key and API Secret from [Last.fm](https://www.last.fm/api/account/create)

## Setup

The setup is performed on your **host machine**, not inside the Docker container.

1.  **Clone or download this repository.**

2.  **Create and configure the credentials file:**
    - Rename the `.env.example` file to `.env`.
    - Open the `.env` file and enter your Last.fm API Key and API Secret.

3.  **Create and activate a Python virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

4.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage (Docker Environment)

This procedure ensures that the script runs safely without interfering with the Navidrome container.

### 1. Find Your Host Paths

Use the `docker inspect` command to find the correct host paths for your data and music folders. Run this on your host machine:

```bash
docker inspect <your_navidrome_container_name_or_id>
```

In the JSON output, look for the `"Mounts"` section. The `"Source"` field is the path on your host machine.

- **Data Path**: Look for the mount where `"Destination"` is `/data`. The corresponding `"Source"` is your host path (often under `/var/lib/docker/volumes/...`).
- **Music Path**: Look for the mount where `"Destination"` is `/music`.

### 2. Run the Update Process

This process requires running the script with `sudo` to access Docker-managed files, but it's crucial to use the Python executable from your virtual environment (`venv`) to ensure all dependencies are found.

**Step 1: Stop the Navidrome container**
This prevents database corruption by ensuring the database file is not in use.
```bash
docker stop <your_navidrome_container_name_or_id>
```

**Step 2: Run the Python script with `sudo`**
Make sure your virtual environment is activated (`source venv/bin/activate`). The command must use the full path to the Python executable within your `venv` directory.
```bash
sudo /path/to/your/project/venv/bin/python3 main.py \
  --db-file "<Source_path_for_data>/navidrome.db" \
  --music-folder "<Source_path_for_music>" \
  --user "YOUR_NAVIDROME_USERNAME"
```
*Replace `/path/to/your/project` with the actual path to the script's directory.*

**Step 3: Restart the Navidrome container**
```bash
docker start <your_navidrome_container_name_or_id>
``` 