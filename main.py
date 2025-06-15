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
        top_tracks = artist.get_top_tracks(limit=limit)
        # Restituisce solo i titoli normalizzati per un confronto più semplice
        return [track.item.title.lower() for track in top_tracks]
    except pylast.WSError as e:
        # Artista non trovato o altro errore API
        # print(f"Attenzione: Impossibile trovare l'artista '{artist_name}' su Last.fm. Errore: {e}")
        return []

def update_play_counts(db_path, username, tracks_to_update, music_folder, boost_plays=1000):
    """Aggiorna il conteggio delle riproduzioni nel database di Navidrome."""
    print(f"Aggiornamento del database: {db_path}")
    print("IMPORTANTE: Assicurati di aver fatto un backup del tuo file navidrome.db prima di continuare!")
    
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
        for track in tqdm(tracks_to_update, desc="Aggiornamento Database"):
            # Costruisci il percorso del file come lo vede Navidrome all'interno del container
            try:
                relative_path = pathlib.Path(track.path).relative_to(music_folder)
                navidrome_path = f"/music/{relative_path.as_posix()}"
            except ValueError:
                print(f"\nAttenzione: Impossibile calcolare il percorso relativo per {track.path}")
                continue

            # Trova l'ID del media_file
            cur.execute("SELECT id FROM media_file WHERE path=?", (navidrome_path,))
            media_file_row = cur.fetchone()

            if not media_file_row:
                # print(f"Attenzione: Traccia non trovata nel DB: {navidrome_path}")
                continue
            
            media_file_id = media_file_row[0]

            # Controlla se esiste già un'annotazione (play count)
            cur.execute("SELECT play_count FROM annotation WHERE media_file_id=? AND user_id=?", (media_file_id, user_id))
            annotation_row = cur.fetchone()

            if annotation_row:
                # Aggiorna il conteggio esistente
                new_play_count = annotation_row[0] + boost_plays
                cur.execute(
                    "UPDATE annotation SET play_count = ?, updated_at = CURRENT_TIMESTAMP WHERE media_file_id=? AND user_id=?",
                    (new_play_count, media_file_id, user_id)
                )
            else:
                # Inserisci una nuova annotazione
                cur.execute(
                    "INSERT INTO annotation (id, user_id, media_file_id, play_count, created_at, updated_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                    (f"{user_id}-{media_file_id}", user_id, media_file_id, boost_plays)
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

    # 4. Per ogni artista, ottenere le top tracce da Last.fm e confrontare
    tracks_to_boost = []
    
    print("Recupero delle top tracce da Last.fm per ogni artista...")
    for artist_name, local_artist_tracks in tqdm(tracks_by_artist.items(), desc="Artisti Processati"):
        top_track_titles = get_top_tracks_for_artist(network, artist_name)
        
        if not top_track_titles:
            continue

        for local_track in local_artist_tracks:
            if local_track.title.lower() in top_track_titles:
                tracks_to_boost.append(local_track)

    print(f"Identificate {len(tracks_to_boost)} tracce da promuovere.")

    # 5. Aggiornare il database di Navidrome
    if tracks_to_boost:
        update_play_counts(args.db_file, args.user, tracks_to_boost, args.music_folder)
    else:
        print("Nessuna traccia da aggiornare.")

    print("--- Script terminato ---")


if __name__ == "__main__":
    main() 