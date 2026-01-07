import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.last.fm"
USER = "k4jgana"


def get_html(url):
    """Fetches HTML content from a URL."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            " AppleWebKit/537.36 (KHTML, like Gecko)"
            " Chrome/123.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text


def scrape_top_artists():
    """
    Scrapes top artist names from the user's Last.fm profile (new layout).

    Returns:
        list[str]: ['Fontaines D.C.', 'The Smiths', 'Unwound', ...]
    """
    url = f"{BASE_URL}/user/{USER}"
    html_content = get_html(url)
    soup = BeautifulSoup(html_content, "html.parser")

    # Restrict search to top artists section only
    artists_section = soup.select_one("section#top-artists")
    if not artists_section:
        return []

    artist_names = [
        tag.get("title", tag.text.strip())
        for tag in artists_section.select("ol.grid-items li.grid-items-item a.link-block-target")
        if tag.get_text(strip=True)
    ]

    return artist_names


def scrape_top_albums():
    """
    Scrapes top albums from the user's Last.fm profile (new layout).
    Returns only album and artist names.

    Returns:
        list[dict]: [{'album': str, 'artist': str}, ...]
    """
    url = f"{BASE_URL}/user/{USER}"
    html_content = get_html(url)
    soup = BeautifulSoup(html_content, "html.parser")

    albums = []
    albums_section = soup.select_one("section#top-albums")
    if not albums_section:
        return albums

    for li in albums_section.select("ol.grid-items li.grid-items-item"):
        album_tag = li.select_one("a.link-block-target")
        artist_tag = li.select_one(".grid-items-item-aux-block")

        if not album_tag:
            continue

        album = album_tag.get("title", album_tag.text.strip())
        artist = artist_tag.get_text(strip=True) if artist_tag else None

        albums.append({"album": album, "artist": artist})

    return albums


# Example usage
if __name__ == "__main__":
    print("TOP ARTISTS:")
    print(scrape_top_artists())

    print("\nTOP ALBUMS:")
    for album in scrape_top_albums():
        print(f"{album['artist']} — {album['album']}")
