import argparse
import os
import pathlib
import sqlite3
import sys

import pylast
from dotenv import load_dotenv
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.oggopus import OggOpus
from tqdm import tqdm

# --- STRUTTURA DATI ---

class Track:
    """Rappresenta un singolo brano musicale locale."""
    def __init__(self, path, artist, title):
        self.path = path
        self.artist = artist
        self.title = title

    def __repr__(self):
        return f"Track(artist='{self.artist}', title='{self.title}')"

# --- FUNZIONI PRINCIPALI ---

def get_lastfm_network(api_key, api_secret):
    """Inizializza e restituisce un oggetto network per interagire con Last.fm."""
    if not api_key or not api_secret:
        print("Errore: API Key e API Secret di Last.fm sono necessari.")
        print("Forniscili tramite argomenti --lastfm-api-key/--lastfm-api-secret o tramite un file .env.")
        sys.exit(1)
    try:
        network = pylast.LastFMNetwork(api_key=api_key, api_secret=api_secret)
        return network
    except pylast.WSError as e:
        print(f"Errore di connessione a Last.fm: {e}")
        sys.exit(1)

def get_local_tracks(music_folder):
    """Scansiona la libreria musicale e restituisce una lista di oggetti Track."""
    print(f"Scansione della cartella musicale in corso: {music_folder}")
    
    music_path = pathlib.Path(music_folder)
    if not music_path.is_dir():
        print(f"Errore: Il percorso specificato non è una directory valida: {music_folder}")
        sys.exit(1)

    files = list(music_path.rglob("*.mp3")) + list(music_path.rglob("*.flac")) + list(music_path.rglob("*.opus"))
    
    tracks = []
    print(f"Trovati {len(files)} file musicali. Analisi dei metadati in corso...")

    for file in tqdm(files, desc="Analisi Metadati"):
        try:
            if file.suffix == ".mp3":
                audio = MP3(file)
                artist = audio.get('TPE1', [None])[0]
                title = audio.get('TIT2', [None])[0]
            elif file.suffix == ".flac":
                audio = FLAC(file)
                artist = audio.get('artist', [None])[0]
                title = audio.get('title', [None])[0]
            elif file.suffix == ".opus":
                audio = OggOpus(file)
                artist = audio.get('artist', [None])[0]
                title = audio.get('title', [None])[0]
            else:
                continue

            if artist and title:
                tracks.append(Track(path=str(file), artist=artist, title=title))
        except Exception as e:
            # Ignora i file che non possono essere letti o non hanno i tag necessari
            # print(f"Attenzione: impossibile leggere i metadati per {file}. Errore: {e}")
            pass

    print(f"Scansione completata. Trovate {len(tracks)} tracce con metadati validi.")
    return tracks


def get_top_tracks_for_artist(network, artist_name, limit=50):
    """Recupera le tracce più popolari per un dato artista da Last.fm."""
    try:
        artist = network.get_artist(artist_name)
        # Restituisce l'intera lista di oggetti TopItem, che contengono titolo e rank
        return artist.get_top_tracks(limit=limit)
    except pylast.WSError as e:
        # Artista non trovato o altro errore API
        return []

def update_play_counts(db_path, username, tracks_to_update, music_folder):
    """Aggiorna il conteggio delle riproduzioni nel database di Navidrome."""
    print(f"Aggiornamento del database: {db_path}")
    
    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()

        # 1. Trova l'ID dell'utente
        cur.execute("SELECT id FROM user WHERE name=?", (username,))
        user_row = cur.fetchone()
        if not user_row:
            print(f"Errore: Utente '{username}' non trovato nel database.")
            con.close()
            return
        user_id = user_row[0]
        print(f"Trovato utente '{username}' con ID: {user_id}")

        # 2. Aggiorna i conteggi per ogni traccia
        updated_count = 0
        for track, score in tqdm(tracks_to_update.items(), desc="Aggiornamento Database"):
            # Costruisci il percorso del file come lo vede Navidrome
            try:
                relative_path = pathlib.Path(track.path).relative_to(music_folder)
                navidrome_path = relative_path.as_posix()
            except ValueError:
                continue

            # Trova l'ID del media_file
            cur.execute("SELECT id FROM media_file WHERE path=?", (navidrome_path,))
            media_file_row = cur.fetchone()

            if not media_file_row:
                continue
            
            media_file_id = media_file_row[0]

            # Controlla se esiste già un'annotazione
            cur.execute("SELECT play_count FROM annotation WHERE item_id=? AND user_id=?", (media_file_id, user_id))
            annotation_row = cur.fetchone()

            if annotation_row:
                # Aggiorna il conteggio esistente con il nuovo punteggio
                cur.execute(
                    "UPDATE annotation SET play_count = ?, play_date = CURRENT_TIMESTAMP WHERE item_id=? AND user_id=?",
                    (score, media_file_id, user_id)
                )
            else:
                # Inserisci una nuova annotazione con il nuovo punteggio
                cur.execute(
                    "INSERT INTO annotation (user_id, item_id, item_type, play_count, play_date) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    (user_id, media_file_id, 'media_file', score)
                )
            updated_count += 1

        con.commit()
        con.close()
        print(f"Aggiornamento completato. {updated_count} tracce sono state aggiornate nel database.")

    except sqlite3.Error as e:
        print(f"Errore del database SQLite: {e}")
        sys.exit(1)


# --- ESECUZIONE SCRIPT ---

def main():
    load_dotenv() # Carica le variabili dal file .env

    parser = argparse.ArgumentParser(
        description="Aggiorna le statistiche di Navidrome con le top track di Last.fm.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        "--db-file",
        required=True,
        help="Percorso del file navidrome.db."
    )
    parser.add_argument(
        "--music-folder",
        required=True,
        help="Percorso della tua cartella musicale principale."
    )
    parser.add_argument(
        "--lastfm-api-key",
        default=os.getenv("LASTFM_API_KEY"),
        help="La tua API key di Last.fm (può essere impostata nel file .env)."
    )
    parser.add_argument(
        "--lastfm-api-secret",
        default=os.getenv("LASTFM_API_SECRET"),
        help="Il tuo API secret di Last.fm (può essere impostato nel file .env)."
    )
    parser.add_argument(
        "--user",
        required=True,
        help="Username di Navidrome per cui aggiornare le statistiche."
    )

    args = parser.parse_args()

    print("--- Avvio script Navidrome Top Tracks ---")
    
    # 1. Connessione a Last.fm
    network = get_lastfm_network(args.lastfm_api_key, args.lastfm_api_secret)
    print("Connessione a Last.fm riuscita.")

    # 2. Scansione della libreria musicale
    local_tracks = get_local_tracks(args.music_folder)
    if not local_tracks:
        print("Nessuna traccia trovata. Lo script termina.")
        return
    
    # 3. Raggruppare le tracce per artista
    print("Raggruppamento delle tracce per artista...")
    tracks_by_artist = {}
    for track in local_tracks:
        if track.artist not in tracks_by_artist:
            tracks_by_artist[track.artist] = []
        tracks_by_artist[track.artist].append(track)
    
    print(f"Trovati {len(tracks_by_artist)} artisti unici.")

    # 4. Per ogni artista, ottenere le top tracce da Last.fm e creare la mappa dei punteggi
    print("Recupero delle top tracce e calcolo dei punteggi ponderati...")
    
    BASE_SCORE = 10000  # Punteggio per la traccia #1
    tracks_to_update = {}

    for artist_name, local_artist_tracks in tqdm(tracks_by_artist.items(), desc="Artisti Processati"):
        # Azzera i punteggi per tutte le canzoni dell'artista in questa esecuzione
        for local_track in local_artist_tracks:
            tracks_to_update[local_track] = 0

        # Ottieni le top tracce da Last.fm
        top_tracks = get_top_tracks_for_artist(network, artist_name)
        if not top_tracks:
            continue

        # Crea una mappa dei titoli per un confronto veloce
        # Usiamo enumerate per ottenere il rank dalla posizione nella lista (partendo da 1)
        lastfm_titles_map = {track.item.title.lower(): i + 1 for i, track in enumerate(top_tracks)}

        # Assegna i punteggi ponderati solo alle hit
        for local_track in local_artist_tracks:
            rank = lastfm_titles_map.get(local_track.title.lower())
            if rank is not None:
                score = BASE_SCORE - (rank - 1)
                tracks_to_update[local_track] = score

    print(f"Identificate {len([s for s in tracks_to_update.values() if s > 0])} tracce da promuovere con punteggio ponderato.")

    # 5. Aggiornare il database di Navidrome
    if tracks_to_update:
        update_play_counts(args.db_file, args.user, tracks_to_update, args.music_folder)
    else:
        print("Nessuna traccia da aggiornare.")

    print("--- Script terminato ---")


if __name__ == "__main__":
    main() 