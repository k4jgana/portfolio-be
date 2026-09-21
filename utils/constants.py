import os
from functools import lru_cache
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from services.letterboxd_service import LetterboxdService
from utils.settings import get_settings

load_dotenv()


CDs = {
    "The Low End Theory": {"artist": "A Tribe Called Quest", "have": True},
    "To Pimp a Butterfly": {"artist": "Kendrick Lamar", "have": True},
    "Dummy": {"artist": "Portishead", "have": True},
    "Mezzanine": {"artist": "Massive Attack", "have": True},
    "Rodeo": {"artist": "Travis Scott", "have": True},
    "xx": {"artist": "The xx", "have": True},
    "Nonagon Infinity": {"artist": "King Gizzard and the Lizard Wizard", "have": True},
    "Funeral": {"artist": "Arcade Fire", "have": True},
    "The College Dropout": {"artist": "Kanye West", "have": True},
    "Remain in Light": {"artist": "Talking Heads", "have": True},
    "Atom Heart Mother": {"artist": "Pink Floyd", "have": True},
    "OK Computer": {"artist": "Radiohead", "have": True},
    "good kid, m.A.A.d city": {"artist": "Kendrick Lamar", "have": True},
    "Aquemini": {"artist": "Outkast", "have": True},
    "Discovery": {"artist": "Daft Punk", "have": True},
    "Rain Dogs": {"artist": "Tom Waits", "have": True},
    "Me Against the World": {"artist": "2Pac", "have": True},
    "The Money Store": {"artist": "Death Grips", "have": True},
    "Illmatic": {"artist": "Nas", "have": True},
    "Beloved! Paradise! Jazz!?": {"artist": "McKinley Dixon", "have": True},
    "Blackstar": {"artist": "David Bowie", "have": True},
    "Safizam": {"artist": "SAF", "have": True},
    "Enter the Wu-Tang (36 Chambers)": {"artist": "Wu-Tang Clan", "have": True},
    "Is This It": {"artist": "The Strokes", "have": True},
    "Plowing in the Field of Love": {"artist": "Iceage", "have": True},
    "IGOR": {"artist": "Tyler, the Creator", "have": True},
    "Room on Fire": {"artist": "The Strokes", "have": False},
    "The New Abnormal": {"artist": "The Strokes", "have": False},
    "Samurai": {"artist": "Lupe Fiasco", "have": False},
    "Imaginal Disk": {"artist": "Magdalena Bay", "have": False},
    "Ants from Up Here": {"artist": "Black Country, New Road", "have": False},
    "LL": {"artist": "The Hellp", "have": False},
    "...Like Clockwork": {"artist": "Queens of the Stone Age", "have": False},
    "It's Album Time": {"artist": "Todd Terje", "have": False},
    "Lift Your Skinny Fists Like Antennas to Heaven": {"artist": "Godspeed You! Black Emperor", "have": False},
    "45:33": {"artist": "LCD Soundsystem", "have": False},
    "Sound of Silver": {"artist": "LCD Soundsystem", "have": False},
    "This Is Happening": {"artist": "LCD Soundsystem", "have": False},
    "Hiding Places": {"artist": "billy woods", "have": False},
    "Maps": {"artist": "billy woods", "have": False},
    "Midnight Marauders": {"artist": "A Tribe Called Quest", "have": False},
    "We Got It from Here... Thank You 4 Your Service": {"artist": "A Tribe Called Quest", "have": False},
    "1999": {"artist": "Joey Bada$$", "have": False},
    "Blonde": {"artist": "Frank Ocean", "have": False},
    "LP!": {"artist": "JPEGMAFIA", "have": False},
    "Veteran": {"artist": "JPEGMAFIA", "have": False},
    "All My Heroes Are Cornballs": {"artist": "JPEGMAFIA", "have": False},
    "I Lay Down My Life for You": {"artist": "JPEGMAFIA", "have": False},
    "ATLiens": {"artist": "Outkast", "have": False},
    "Donuts": {"artist": "J Dilla", "have": False},
    "Atrocity Exhibition": {"artist": "Danny Brown", "have": False},
    "Scaring the Hoes": {"artist": "JPEGMAFIA & Danny Brown", "have": False},
    "Black on Both Sides": {"artist": "Mos Def", "have": False},
    "Unknown Pleasures": {"artist": "Joy Division", "have": False},
    "Deltron 3030": {"artist": "Deltron 3030", "have": False},
    "Die Lit": {"artist": "Playboi Carti", "have": False},
    "Endtroducing.....": {"artist": "DJ Shadow", "have": False},
    "F#A#∞": {"artist": "Godspeed You! Black Emperor", "have": False},
    "Speaking in Tongues": {"artist": "Talking Heads", "have": False},
    "Flying Microtonal Banana": {"artist": "King Gizzard and the Lizard Wizard", "have": False},
    "The Suburbs": {"artist": "Arcade Fire", "have": False},
    "The Rise and Fall of Ziggy Stardust": {"artist": "David Bowie", "have": False},
    "Saturation 2": {"artist": "Brockhampton", "have": False},
    "Since I Left You": {"artist": "The Avalanches", "have": False},
    "Vtora mladost, treta svetska vojna": {"artist": "Bernays Propaganda", "have": False},
    "Yankee Hotel Foxtrot": {"artist": "Wilco", "have": False},
    "4eva Is a Mighty Long Time": {"artist": "Big K.R.I.T.", "have": False},
    "By the Time I Get to Phoenix": {"artist": "Injury Reserve", "have": False},
    "Carrie & Lowell": {"artist": "Sufjan Stevens", "have": False},
    "Below the Heavens": {"artist": "Blu & Exile", "have": False},
    "Cave World": {"artist": "Viagra Boys", "have": False},
}


settings = get_settings()
MASTER_EMAIL = settings.master_email
OPENAI_API_KEY = settings.openai_api_key
PINECONE_API_KEY = settings.pinecone_api_key
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")
PINECONE_INDEX = settings.pinecone_index
NAMESPACE = settings.namespace
SPOTIFY_CLIENT_ID = settings.spotify_client_id
SPOTIFY_CLIENT_SECRET = settings.spotify_client_secret
SPOTIFY_REDIRECT_URI = settings.spotify_redirect_uri
SPOTIFY_REFRESH_TOKEN = settings.spotify_refresh_token
DEFAULT_MODEL = settings.model_name


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=OPENAI_API_KEY)


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=DEFAULT_MODEL,
        temperature=settings.model_temperature,
        timeout=settings.model_timeout_seconds,
        max_retries=settings.model_max_retries,
    )


@lru_cache(maxsize=1)
def get_vector_store() -> PineconeVectorStore:
    return PineconeVectorStore.from_existing_index(
        index_name=PINECONE_INDEX,
        embedding=get_embeddings(),
        namespace=NAMESPACE,
    )


@lru_cache(maxsize=1)
def get_letterboxd_service() -> LetterboxdService:
    return LetterboxdService()


def get_spotify_client():
    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=(
            "user-library-read "
            "user-top-read "
            "user-read-recently-played "
            "user-read-private "
            "user-read-email"
        ),
        open_browser=False,
        cache_path=None
    )

    token_info = auth_manager.refresh_access_token(SPOTIFY_REFRESH_TOKEN)
    access_token = token_info["access_token"]
    return spotipy.Spotify(
        auth=access_token,
        requests_timeout=15,
        retries=2,
        status_retries=2,
    )
