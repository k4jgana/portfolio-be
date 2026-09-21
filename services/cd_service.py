from sqlalchemy import func

from persistence import CD, get_db_session


def _find_cd(db, album: str, artist: str | None = None):
    query = db.query(CD).filter(func.lower(CD.name) == album.strip().lower())
    if artist is not None:
        query = query.filter(func.lower(CD.artist) == artist.strip().lower())
    return query.first()


def get_cds() -> str:
    return "\n".join(
        f"{cd['artist']} - {cd['album']} - {str(cd['have']).lower()}"
        for cd in get_cd_records()
    )


def get_cd_records() -> list[dict]:
    """Return the collection as records suitable for internal tool results."""
    db = get_db_session()
    try:
        cds = db.query(CD).order_by(CD.id).all()
        return [
            {"id": cd.id, "artist": cd.artist, "album": cd.name, "have": cd.have}
            for cd in cds
        ]
    finally:
        db.close()


def set_have(artist: str, album: str, have: bool):
    db = get_db_session()
    try:
        cd = _find_cd(db, album, artist)
        if not cd:
            return {"status": "not_found", "message": "CD not found."}
        cd.have = have
        db.commit()
        return {
            "status": "success",
            "message": f"Updated '{cd.artist} - {cd.name}' ownership status.",
        }
    finally:
        db.close()


def add_cd(artist: str, album: str, have: bool = False):
    db = get_db_session()
    try:
        if _find_cd(db, album, artist):
            return {"status": "exists", "message": "That CD already exists."}
        cd = CD(name=album.strip(), artist=artist.strip(), have=have)
        db.add(cd)
        db.commit()
        return {"status": "success", "message": f"Added '{cd.artist} - {cd.name}'."}
    finally:
        db.close()
