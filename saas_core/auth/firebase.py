import logging
from typing import Optional, Dict, Any
import firebase_admin
from firebase_admin import auth, credentials

from saas_core.config.settings import get_saas_settings
from saas_core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

_firebase_initialized = False


def init_firebase() -> None:
    """
    Initializes the Firebase Admin SDK idempotently.
    Reads credentials from settings or defaults to Application Default Credentials.
    """
    global _firebase_initialized
    if _firebase_initialized:
        return

    # Check if default app is already initialized in firebase_admin
    try:
        firebase_admin.get_app()
        _firebase_initialized = True
        logger.info("Firebase Admin SDK already initialized.")
        return
    except ValueError:
        pass

    settings = get_saas_settings()
    cred = None

    if settings.FIREBASE_CREDENTIALS_PATH:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
    elif settings.FIREBASE_PRIVATE_KEY and settings.FIREBASE_CLIENT_EMAIL and settings.FIREBASE_PROJECT_ID:
        # Replace escaped newlines if passed via environment variables
        private_key = settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n")
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": settings.FIREBASE_PROJECT_ID,
            "private_key": private_key,
            "client_email": settings.FIREBASE_CLIENT_EMAIL,
            "token_uri": "https://oauth2.googleapis.com/token",
        })

    if cred:
        firebase_admin.initialize_app(cred)
    else:
        # Fall back to ADC / emulator / project ID if provided
        options = {}
        if settings.FIREBASE_PROJECT_ID:
            options["projectId"] = settings.FIREBASE_PROJECT_ID
        firebase_admin.initialize_app(options=options)

    _firebase_initialized = True
    logger.info("Firebase Admin SDK initialized successfully.")


def verify_firebase_id_token(id_token: str, check_revoked: bool = False) -> Dict[str, Any]:
    """
    Verifies a Firebase ID token.
    Returns the decoded token claims dictionary.
    Raises AuthenticationError if invalid or expired.
    """
    init_firebase()
    try:
        decoded_token = auth.verify_id_token(id_token, check_revoked=check_revoked)
        return decoded_token
    except auth.ExpiredIdTokenError as e:
        logger.warning("Firebase ID token expired")
        raise AuthenticationError("Authentication token has expired") from e
    except auth.RevokedIdTokenError as e:
        logger.warning("Firebase ID token revoked")
        raise AuthenticationError("Authentication token has been revoked") from e
    except auth.InvalidIdTokenError as e:
        logger.warning("Invalid Firebase ID token: %s", str(e))
        raise AuthenticationError("Invalid authentication token") from e
    except Exception as e:
        logger.error("Unexpected error during Firebase token verification: %s", str(e))
        raise AuthenticationError("Authentication verification failed") from e
