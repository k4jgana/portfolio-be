from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from utils.constants import DATABASE_URL
from schemas import CD


engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()



def get_cds():
    cds = session.query(CD).all()
    return "\n".join(f"{cd.artist} - {cd.album} - {str(cd.have).lower()}" for cd in cds)

# Update 'have' field
def set_have(artist: str, album: str, have: bool):
    cd = session.query(CD).filter(
        CD.artist.ilike(artist), CD.album.ilike(album)
    ).first()
    if not cd:
        return 'CD not found'
    cd.have = have
    session.commit()


def add_cd(artist: str, album: str, have: bool = False):
    existing_cd = session.query(CD).filter(
        CD.artist.ilike(artist),
        CD.album.ilike(album)
    ).first()

    if existing_cd:
        return f"CD '{artist} - {album}' already exists."
    new_cd = CD(artist=artist, album=album, have=have)
    session.add(new_cd)
    session.commit()

