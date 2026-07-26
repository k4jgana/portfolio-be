import json
import logging
import os

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

logger = logging.getLogger(__name__)


def initialize_firebase() -> bool:
    if firebase_admin._apps:
        return True

    credentials_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    credentials_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

    try:
        if credentials_json:
            payload = json.loads(credentials_json)
            firebase_admin.initialize_app(credentials.Certificate(payload))
            return True

        if credentials_path:
            firebase_admin.initialize_app(credentials.Certificate(credentials_path))
            return True

        logger.warning("Firebase admin credentials are not configured.")
        return False
    except Exception:
        logger.exception("Failed to initialize Firebase admin SDK.")
        return False


def verify_id_token(id_token: str) -> dict:
    if not id_token or not id_token.strip():
        raise ValueError("Missing Firebase ID token.")

    if not initialize_firebase():
        raise ValueError("Firebase admin SDK is not configured.")

    return firebase_auth.verify_id_token(id_token.strip())
