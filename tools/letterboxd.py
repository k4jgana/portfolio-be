import random
import logging
from langchain.tools import tool
from utils.constants import lb

logger = logging.getLogger(__name__)



@tool
def get_movie_ratings_by_year(year: int = 2013) -> str:
    """
    Returns Nenad's movie ratings from a certain year

    Args:
        limit: Number of recent watched movies to retrieve (default 30)

    Returns:
        A formatted string listing recent rated movies with rating and month
    """
    logger.info(f"[MovieAgent][get_movie_ratings_by_year] tool called")

    try:
        recs = lb.get_ratings_by_year(year=year)
    except Exception as e:
        logger.exception("Failed to fetch recent ratings")
        return f"Error fetching recent ratings: {e}"

    if not recs:
        return "No recent ratings found."

    output_lines = [
        f"{i+1}. {item.get('title','Unknown Title')} - Rating: {item.get('rating','N/A')} - Month: {item.get('month','N/A')}"
        for i, item in enumerate(recs)
    ]
    return "\n".join(output_lines)



@tool
def get_recent_movie_ratings(limit: int = 30) -> str:
    """
    Returns Nenad's most recent movie ratings

    Args:
        limit: Number of recent watched movies to retrieve (default 30)

    Returns:
        A formatted string listing recent rated movies with rating and month
    """
    logger.info(f"[MovieAgent][get_recent_movie_ratings] tool called")

    try:
        recs = lb.get_recent_ratings(limit=limit)
    except Exception as e:
        logger.exception("Failed to fetch recent ratings")
        return f"Error fetching recent ratings: {e}"

    if not recs:
        return "No recent ratings found."

    output_lines = [
        f"{i+1}. {item.get('title','Unknown Title')} - Rating: {item.get('rating','N/A')} - Month: {item.get('month','N/A')}"
        for i, item in enumerate(recs[:limit])
    ]
    return "\n".join(output_lines)


@tool
def get_genre_recommendations(genre: str = "thriller", limit: int = 5) -> str:
    """
    Returns top-rated movies for a given genre.

    Args:
        genre: Genre to filter by (default 'thriller')
        limit: Number of movies to retrieve (default 5)

    Returns:
        A formatted string listing the top movies for that genre
    """
    logger.info(f"[MovieAgent][get_genre_recommendations] tool called - genre={genre} limit={limit}")

    try:
        results = lb.get_ratings_by_genre(genre=genre)
    except Exception as e:
        logger.exception("Failed to fetch genre ratings")
        return f"Error fetching ratings for genre '{genre}': {e}"

    if not results:
        return f"No movies found for genre '{genre}'."

    random.shuffle(results)

    output_lines = [
        f"{i+1}. {movie.get('title','Unknown Title')} - Rating: {movie.get('rating','N/A')} - Genre: {movie.get('genre', genre)}"
        for i, movie in enumerate(results[:limit])
    ]
    return "\n".join(output_lines)


@tool
def get_personal_picks(n: int = 5) -> str:
    """
    Returns N random movies from Nenad's personal picks.

    Args:
        n: Number of personal picks to return (default 5)

    Returns:
        A formatted string listing random personal picks with ratings
    """
    logger.info(f"[MovieAgent][get_personal_picks] tool called - n={n}")

    try:
        picks = lb.get_nenad_personal_picks()
    except Exception as e:
        logger.exception("Failed to fetch personal picks")
        return f"Error fetching personal picks: {e}"

    if not picks:
        return "No personal picks found."

    # If n is larger than available picks, just return all (shuffled)
    random.shuffle(picks)
    selected = picks[:n]

    output_lines = [
        f"{i+1}. {m.get('title','Unknown Title')} - Rating: {m.get('rating','N/A')}"
        for i, m in enumerate(selected)
    ]
    return "\n".join(output_lines)
