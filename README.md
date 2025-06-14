# Navidrome Top Tracks Updater

This script updates the play count statistics of your Navidrome server to ensure that an artist's "Top Tracks" section reflects their actual popular hits, based on data from Last.fm.

## Prerequisites

- Python 3.8+
- A working Navidrome installation
- An API Key and API Secret from [Last.fm](https://www.last.fm/api/account/create)

## Setup

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

## Usage

**IMPORTANT:** Before running the script, it is strongly recommended to back up your Navidrome database (`navidrome.db`).

Run the script with the following command, replacing the paths and your username:

```bash
python3 main.py \
  --db-file "/path/to/your/navidrome.db" \
  --music-folder "/path/to/your/music" \
  --user "YOUR_NAVIDROME_USERNAME"
```

After the script finishes, you may need to restart the Navidrome service to see the changes. 