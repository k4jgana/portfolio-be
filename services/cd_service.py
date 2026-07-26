from utils.constants import CDs


def _find_cd(album: str, artist: str | None = None):
    normalized_album = album.strip().casefold()
    normalized_artist = artist.strip().casefold() if artist is not None else None

    for existing_album, details in CDs.items():
        if existing_album.strip().casefold() != normalized_album:
            continue
        if normalized_artist is not None and details["artist"].strip().casefold() != normalized_artist:
            continue
        return existing_album, details

    return None, None



def get_cds():
    return "\n".join(
        f"{details['artist']} - {album} - {str(details['have']).lower()}"
        for album, details in CDs.items()
    )

# Update 'have' field
def set_have(artist: str, album: str, have: bool):
    _, cd = _find_cd(album, artist)
    if not cd:
        return 'CD not found'
    cd["have"] = have


def add_cd(artist: str, album: str, have: bool = False):
    existing_album, _ = _find_cd(album, artist)

    if existing_album:
        return f"CD '{artist} - {album}' already exists."
    CDs[album] = {"artist": artist, "have": have}

