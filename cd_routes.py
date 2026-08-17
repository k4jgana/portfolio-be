import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth_verifier import verify_id_token
from persistence import CD, get_db_session
from schemas import CDCreate, CDResponse, CDUpdate

router = APIRouter(prefix="/cd-api", tags=["CD manager"])

def _extract_bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "").strip()
    if not authorization.lower().startswith("bearer "):
        return None
    return authorization[7:].strip() or None


def require_cd_auth(request: Request) -> dict:
    admin_email = (os.getenv("CD_ADMIN_EMAIL") or os.getenv("MASTER_EMAIL", "")).strip().lower()
    if not admin_email:
        raise HTTPException(status_code=503, detail="CD manager is not configured.")

    id_token = _extract_bearer_token(request)
    if not id_token:
        raise HTTPException(status_code=401, detail="Authentication required.")

    try:
        claims = verify_id_token(id_token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token.") from exc

    email = (claims.get("email") or "").strip().lower()
    sign_in_provider = claims.get("firebase", {}).get("sign_in_provider")
    if (
        not claims.get("email_verified")
        or email != admin_email
        or sign_in_provider != "google.com"
    ):
        raise HTTPException(status_code=403, detail="This Google account is not authorized.")
    return claims


def _db() -> Session:
    try:
        return get_db_session()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="CD database is temporarily unavailable.") from exc


def _duplicate(db: Session, name: str, artist: str, excluded_id: int | None = None) -> bool:
    query = db.query(CD.id).filter(
        func.lower(CD.name) == name.lower(),
        func.lower(CD.artist) == artist.lower(),
    )
    if excluded_id is not None:
        query = query.filter(CD.id != excluded_id)
    return query.first() is not None


@router.get("/session", dependencies=[Depends(require_cd_auth)])
def session_status(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"authenticated": True}


@router.get("/cds", response_model=list[CDResponse], dependencies=[Depends(require_cd_auth)])
def list_cds():
    db = _db()
    try:
        return db.query(CD).order_by(CD.id).all()
    finally:
        db.close()


@router.post(
    "/cds",
    response_model=CDResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_cd_auth)],
)
def create_cd(payload: CDCreate):
    db = _db()
    try:
        if _duplicate(db, payload.name, payload.artist):
            raise HTTPException(status_code=409, detail="That CD is already listed.")
        cd = CD(name=payload.name, artist=payload.artist, have=payload.have)
        db.add(cd)
        db.commit()
        db.refresh(cd)
        return cd
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="That CD is already listed.") from exc
    finally:
        db.close()


@router.put("/cds/{cd_id}", response_model=CDResponse, dependencies=[Depends(require_cd_auth)])
def update_cd(cd_id: int, payload: CDUpdate):
    db = _db()
    try:
        cd = db.get(CD, cd_id)
        if cd is None:
            raise HTTPException(status_code=404, detail="CD not found.")
        if _duplicate(db, payload.name, payload.artist, excluded_id=cd_id):
            raise HTTPException(status_code=409, detail="That CD is already listed.")
        cd.name = payload.name
        cd.artist = payload.artist
        cd.have = payload.have
        db.commit()
        db.refresh(cd)
        return cd
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="That CD is already listed.") from exc
    finally:
        db.close()


@router.delete(
    "/cds/{cd_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_cd_auth)],
)
def delete_cd(cd_id: int):
    db = _db()
    try:
        cd = db.get(CD, cd_id)
        if cd is None:
            raise HTTPException(status_code=404, detail="CD not found.")
        db.delete(cd)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    finally:
        db.close()
