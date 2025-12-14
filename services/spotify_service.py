from utils.constants import spotify as sp
from collections import Counter




from collections import Counter
from datetime import datetime

def get_albums(top=10):
    """
    Returns albums that appear more than 3 times in liked songs,
    sorted by most recently added_at.
    """
    liked = get_liked_songs(num_songs=300)

    if not liked:
        return []

    album_counter = Counter()
    album_info = {}
    album_latest_added = {}

    for item in liked:
        added_at = item.get("added_at")
        track = item["track"]
        album = track["album"]

        album_name = album["name"]
        artist_name = album["artists"][0]["name"]

        # Count occurrences
        album_counter[album_name] += 1

        # Track most recent added_at
        if added_at:
            added_dt = datetime.fromisoformat(added_at.replace("Z", "+00:00"))

            if (
                album_name not in album_latest_added
                or added_dt > album_latest_added[album_name]
            ):
                album_latest_added[album_name] = added_dt

        # Store album metadata once
        if album_name not in album_info:
            album_info[album_name] = {
                "album_name": album_name,
                "artist": artist_name,
                "album_id": album["id"],
                "cover": album["images"][0]["url"] if album["images"] else None,
            }

    # Filter albums with count > 3
    filtered_albums = [
        album_name
        for album_name, count in album_counter.items()
        if count > 3
    ]

    # Sort by most recent added_at
    sorted_albums = sorted(
        filtered_albums,
        key=lambda name: album_latest_added.get(name, datetime.min),
        reverse=True
    )

    # Build final response
    result = []
    for album_name in sorted_albums[:top]:
        info = album_info[album_name].copy()
        info["count"] = album_counter[album_name]
        info["latest_added_at"] = album_latest_added[album_name].isoformat()
        result.append(info)

    return result



def get_liked_songs(num_songs=50):
    """
    Returns up to `num_songs` liked (saved) tracks.
    Handles Spotify's 50-item request limit by paging.
    """
    liked = []
    limit = 50  # Spotify max allowed
    offset = 0

    while len(liked) < num_songs:
        results = sp.current_user_saved_tracks(
            limit=min(limit, num_songs - len(liked)),
            offset=offset
        )

        items = results.get("items", [])
        if not items:
            break  # no more songs available

        liked.extend(items)
        offset += limit  # move to next page

    return liked[:num_songs]



def get_top_tracks_all_time(limit=50, time_filter='short_term'):
    """
    Returns the user's top tracks (long_term = all time).
    """
    results = sp.current_user_top_tracks(time_range=time_filter, limit=limit)
    return results.get("items", [])


if __name__ == "__main__":
    x = get_albums(30)
    for el in x:
        print(el['album_name'])
