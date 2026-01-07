import random, logging
from langchain.tools import tool
from services.spotify_service import get_albums, get_liked_songs, get_spotify_client
from services.lastfm_service import scrape_top_albums, scrape_top_artists

logger = logging.getLogger(__name__)


@tool
def get_album_recommendations(num: int = 5) -> str:
    """
    Returns the Nenad's top recent albums from Spotify and formats them nicely.
    He recommends these albums


    Args:
        num: Number of albums to retrieve (default 5)

    Returns:
        A formatted string listing the top albums and their artists
    """

    logger.info(f"[MusicAgent][get_album_recommendations] tool called")

    recs = scrape_top_albums()
    if not recs:
        return "No albums found."
    output_lines = [f"{i+1}. {album['album']} - {album['artist']}" for i, album in enumerate(recs[:num])]
    return "\n".join(output_lines)


@tool
def get_artist_recommendations(limit: int = 10, time_filter: str = "short_term") -> str:
    """
    Returns the Nenad's recent top artists from Spotify.
    He recommends these artists

    Args:
        limit: Number of artists to retrieve (default 10)
        time_filter: Time range for top artists (short_term, medium_term, long_term)

    Returns:
        A formatted string listing the top artists
    """

    logger.info(f"[MusicAgent][get_artist_recommendations] tool called")

    results = scrape_top_artists()
    if not results:
        return "No artists found."
    output_lines = [f"{i + 1}. {artist}" for i, artist in enumerate(results)]
    return "\n".join(output_lines)


@tool
def get_song_recommendations(k: int = 10) -> str:
    """
    Returns k random songs from the user's liked songs on Spotify.

    Args:
        k: Number of songs to retrieve (default 5)

    Returns:
        A formatted string listing the songs and their artists
    """

    logger.info(f"[MusicAgent][get_song_recommendations] tool called")

    songs = get_liked_songs(num_songs=300)
    random.shuffle(songs)
    selected_songs = songs[:k]
    return "\n".join([f"{song['track']['name']} - {song['track']['artists'][0]['name']}" for song in selected_songs])
