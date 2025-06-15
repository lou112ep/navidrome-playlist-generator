#!/bin/bash

# --- CONFIGURAZIONE ---
# Assicurati che questo percorso sia corretto.
PROJECT_DIR="/home/luca/scripts/navidrome-playlist-generator"
LOG_FILE="$PROJECT_DIR/updater_cron.log"

# Dettagli dello script e del container
DB_FILE="/var/lib/docker/volumes/7746832b924d1b77fd5789addede95265b910b6c55155fa0f1209f1386a9c76c/_data/navidrome.db"
MUSIC_FOLDER="/home/luca/cloud/luca/files/music"
NAVI_USER="luca"
CONTAINER_NAME="navidrome"
PYTHON_EXEC="$PROJECT_DIR/venv/bin/python3"

# --- ESECUZIONE ---

# Vai alla directory del progetto per caricare il .env e usare i percorsi relativi
cd "$PROJECT_DIR" || exit 1

# Reindirizza tutto l'output (stdout e stderr) al file di log
exec >> "$LOG_FILE" 2>&1

echo "======================================================"
echo "--- Inizio Cron Job: $(date) ---"
echo "======================================================"

echo "Passo 1: Fermare il container Navidrome..."
if docker stop "$CONTAINER_NAME"; then
    echo "Container '$CONTAINER_NAME' fermato con successo."
    sleep 5 # Pausa per sicurezza
else
    echo "ERRORE: Impossibile fermare il container '$CONTAINER_NAME'."
    exit 1
fi

echo "Passo 2: Eseguire lo script di aggiornamento con sudo..."
if sudo "$PYTHON_EXEC" main.py --db-file "$DB_FILE" --music-folder "$MUSIC_FOLDER" --user "$NAVI_USER"; then
    echo "Script Python eseguito con successo."
else
    echo "ERRORE: L'esecuzione dello script Python è fallita."
    # Si tenta comunque di riavviare Navidrome nel passo successivo
fi

echo "Passo 3: Riavviare il container Navidrome..."
if docker start "$CONTAINER_NAME"; then
    echo "Container '$CONTAINER_NAME' riavviato con successo."
else
    echo "ERRORE: Impossibile riavviare il container '$CONTAINER_NAME'."
fi

echo "--- Fine Cron Job: $(date) ---"
echo "" 