import requests
from bs4 import BeautifulSoup


LETTERBOXD_URL = 'https://letterboxd.com/k4jgana/'

class LetterboxdService:
    STAR_MAP = {
        "★★★★★": 5.0,
        "★★★★½": 4.5,
        "★★★★": 4.0,
        "★★★½": 3.5,
        "★★★": 3.0,
        "★★½": 2.5,
        "★★": 2.0,
        "★½": 1.5,
        "★": 1.0,
        "½": 0.5,
    }

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        }

    def _parse_rating(self, span):
        """Extract numeric rating from Letterboxd rating span."""
        if span is None:
            return None

        text = span.get_text(strip=True)

        # direct glyph mapping
        if text in self.STAR_MAP:
            return self.STAR_MAP[text]

        # fallback: rated-X class
        for c in span.get("class", []):
            if c.startswith("rated-"):
                try:
                    n = int(c.split("-")[1])
                    return n / 2.0
                except Exception:
                    pass

        return None


    # -----------------------------
    #  SCRAPE RECENT DIARY ENTRIES
    # -----------------------------
    def get_recent_ratings(self, limit=30, month =None):
        base_url = f"{LETTERBOXD_URL}diary/films/"
        resp = requests.get(base_url, headers=self.headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        current_month = None

        rows = soup.select("tr.diary-entry-row")

        for tr in rows:
            if len(results) >= limit:
                break

            # --- MONTH (carry down) ---
            month_elem = tr.select_one("td.col-monthdate a.month")
            if month_elem:
                current_month = month_elem.get_text(strip=True)

            # --- TITLE ---
            title_elem = tr.select_one("h2.name a")
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)

            # --- RATING ---
            rating_span = (
                tr.select_one("td.col-rating span.rating")
                or tr.select_one("div.hide-for-owner span.rating")
            )
            rating = self._parse_rating(rating_span)

            # --- LINK ---
            link_elem = title_elem
            movie_link = None
            if link_elem and link_elem.get("href"):
                movie_link = f"https://letterboxd.com{link_elem['href']}".replace("/k4jgana",'')
            description = self.get_movie_description(movie_link)

            results.append({
                "title": title,
                "rating": rating,
                "month": current_month,
                "description":description
            })

        return results


    # ----------------------------------------------------------
    #  NEW: GET MOVIES BY GENRE WITH MINIMUM RATING THRESHOLD
    # ----------------------------------------------------------
    def get_ratings_by_genre(self, genre: str, min_rating: float = 3.5):
        """
        Scrape the Letterboxd genre page for the user in LETTERBOXD_URL and
        return movies with rating > min_rating.

        Fallbacks used to find title:
          - span.frame-title
          - div.react-component[data-item-name]
          - div.react-component[data-item-full-display-name]
          - img[alt]
        """
        url = f"{LETTERBOXD_URL}films/genre/{genre}/by/entry-rating/"
        resp = requests.get(url, headers=self.headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        items = soup.select("li.griditem")

        for li in items:
            # --- TITLE: try multiple fallbacks ---
            title = None

            # 1) visible frame-title (sometimes empty)
            ft = li.select_one("span.frame-title")
            if ft and ft.get_text(strip=True):
                title = ft.get_text(strip=True)

            # 2) react-component data attributes
            if not title:
                rc = li.select_one("div.react-component")
                if rc:
                    # data-item-name or data-item-full-display-name
                    title = rc.get("data-item-name") or rc.get("data-item-full-display-name")

            # 3) img alt attribute
            if not title:
                img = li.select_one("img")
                if img and img.get("alt"):
                    title = img.get("alt")

            if not title:
                # give up on this item
                continue

            # --- RATING ---
            rating_span = li.select_one("p.poster-viewingdata span.rating") or li.select_one("span.rating")
            rating = self._parse_rating(rating_span)

            if rating is None:
                continue

            if rating > min_rating:
                results.append({"title": title, "rating": rating, "genre": genre})

        return results

    def get_ratings_by_year(self, year: int, min_rating: float = 3.5):
        """
        Scrape the Letterboxd year page for the user in LETTERBOXD_URL and
        return movies with rating > min_rating.

        URL example:
          https://letterboxd.com/USERNAME/films/year/2020/

        Title fallbacks (same as genre):
          1. span.frame-title
          2. div.react-component[data-item-name]
          3. div.react-component[data-item-full-display-name]
          4. img[alt]
        """
        url = f"{LETTERBOXD_URL}films/year/{year}/by/entry-rating/"
        resp = requests.get(url, headers=self.headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        items = soup.select("li.griditem")

        for li in items:
            # --- TITLE ---
            title = None

            # 1) frame-title
            ft = li.select_one("span.frame-title")
            if ft and ft.get_text(strip=True):
                title = ft.get_text(strip=True)

            # 2) data-item-name or data-item-full-display-name
            if not title:
                rc = li.select_one("div.react-component")
                if rc:
                    title = rc.get("data-item-name") or rc.get("data-item-full-display-name")

            # 3) img alt
            if not title:
                img = li.select_one("img")
                if img and img.get("alt"):
                    title = img.get("alt")

            if not title:
                continue

            # --- RATING ---
            rating_span = li.select_one("p.poster-viewingdata span.rating") or li.select_one("span.rating")
            rating = self._parse_rating(rating_span)

            if rating is None:
                continue

            if rating > min_rating:
                results.append({
                    "title": title,
                    "rating": rating,
                    "year": year,
                })

        return results

    def get_nenad_personal_picks(self, max_pages: int = 50):
        """
        Scrape all liked films from:
          https://letterboxd.com/<user>/likes/films/
        Follows pagination (/page/2/, /page/3/, ...) until no more results or max_pages reached.
        Returns list of dicts: {"title": ..., "rating": ..., "page": ...}
        """
        base = f"{LETTERBOXD_URL}likes/films/"
        results = []

        for page in range(1, max_pages + 1):
            url = base if page == 1 else f"{base}page/{page}/"
            resp = requests.get(url, headers=self.headers, timeout=15)

            # stop if page doesn't exist
            if resp.status_code == 404:
                break

            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # likes use posteritem; include griditem for robustness
            items = soup.select("li.posteritem, li.griditem")
            if not items:
                break

            for li in items:
                # ----- TITLE FALLBACKS -----
                title = None

                # 1) visible frame-title
                ft = li.select_one("span.frame-title")
                if ft and ft.get_text(strip=True):
                    title = ft.get_text(strip=True)

                # 2) react-component data attributes
                if not title:
                    rc = li.select_one("div.react-component")
                    if rc:
                        title = rc.get("data-item-name") or rc.get("data-item-full-display-name")

                # 3) a.frame data-original-title
                if not title:
                    a_frame = li.select_one("a.frame")
                    if a_frame and a_frame.get("data-original-title"):
                        title = a_frame.get("data-original-title")

                # 4) img alt (strip "Poster for " if present)
                if not title:
                    img = li.select_one("img")
                    if img and img.get("alt"):
                        alt = img.get("alt")
                        if alt.lower().startswith("poster for "):
                            title = alt[len("Poster for "):].strip()
                        else:
                            title = alt.strip()

                if not title:
                    # couldn't find a title, skip
                    continue

                # ----- RATING -----
                rating_span = li.select_one("p.poster-viewingdata span.rating") or li.select_one("span.rating")
                rating = self._parse_rating(rating_span)

                results.append({
                    "title": title,
                    "rating": rating,
                })

        return results

    def get_movie_description(self, url: str) -> str:
        """
        Scrape the movie description from a Letterboxd movie page.

        Args:
            url (str): Full URL of the Letterboxd movie page.

        Returns:
            str: Movie description paragraph. Empty string if not found.
        """
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"Error fetching URL: {e}")
            return ""

        soup = BeautifulSoup(resp.text, "html.parser")

        # Select the production-synopsis section
        synopsis_section = soup.select_one("section.production-synopsis div.truncate p")
        if synopsis_section:
            return synopsis_section.get_text(strip=True)

        return ""





