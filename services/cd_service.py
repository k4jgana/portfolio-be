from sqlalchemy import func

from persistence import CD, get_db_session


def _find_cd(db, album: str, artist: str | None = None):
    query = db.query(CD).filter(func.lower(CD.name) == album.strip().lower())
    if artist is not None:
        query = query.filter(func.lower(CD.artist) == artist.strip().lower())
    return query.first()


def get_cds() -> str:
    db = get_db_session()
    try:
        cds = db.query(CD).order_by(CD.id).all()
        return "\n".join(
            f"{cd.artist} - {cd.name} - {str(cd.have).lower()}"
            for cd in cds
        )
    finally:
        db.close()


def set_have(artist: str, album: str, have: bool):
    db = get_db_session()
    try:
        cd = _find_cd(db, album, artist)
        if not cd:
            return "CD not found"
        cd.have = have
        db.commit()
        return f"Updated '{artist} - {album}' have status to {have}."
    finally:
        db.close()


def add_cd(artist: str, album: str, have: bool = False):
    db = get_db_session()
    try:
        if _find_cd(db, album, artist):
            return f"CD '{artist} - {album}' already exists."
        db.add(CD(name=album.strip(), artist=artist.strip(), have=have))
        db.commit()
        return f"Added CD: {artist} - {album} (have={have})"
    finally:
        db.close()
