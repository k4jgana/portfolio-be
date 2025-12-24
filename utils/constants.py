import os
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from services.letterboxd_service import LetterboxdService

load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")
MASTER_EMAIL = os.getenv("MASTER_EMAIL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")
PINECONE_INDEX = "nenad-info"
NAMESPACE = os.getenv("NAMESPACE", "default")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")
embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=OPENAI_API_KEY)

DEFAULT_MODEL = "gpt-4o-mini"
llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=0.2)

vector_store = PineconeVectorStore.from_existing_index(
    index_name=PINECONE_INDEX,
    embedding=embeddings,
    namespace=NAMESPACE
)


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
spotify = spotipy.Spotify(auth=access_token)


lb = LetterboxdService()



available_paths = {
    "knowledge": "Use this path when the user asks questions specifically about "
                 "Nenad Kajgana, his career, beliefs and etc.",
    "music":"Use this path when the user asks questions specifically about "
            "music related stuff, recommendations, top artists/albums of Nenad Kajgana etc "
            "Basically anything music related",
    "movie":"Use this path when the user asks questions specifically about "
            "movie related stuff, recommendations, top movies of Nenad Kajgana, his personal favorites etc "
            "Basically anything movie related"
}

