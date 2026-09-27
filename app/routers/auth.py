from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.database import get_session
from app.models import User, GoogleCredential
import os

# Google sometimes returns slightly different scope strings (aliases), which crashes oauthlib.
# This environment variable tells oauthlib to relax and accept whatever scopes Google granted.
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

router = APIRouter(prefix="/auth", tags=["auth"])

CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
    "https://www.googleapis.com/auth/classroom.announcements",
    "https://www.googleapis.com/auth/classroom.rosters.readonly"
]

@router.get("/login")
def login(request: Request):
    # This must match one of the redirect URIs in credentials.json exactly
    redirect_uri = str(request.url_for("auth_callback"))

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=redirect_uri
    )

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )

    request.session["state"] = state
    # Save the PKCE code verifier (now required by modern OAuth2 for all app types)
    if hasattr(flow, "code_verifier"):
        request.session["code_verifier"] = getattr(flow, "code_verifier")

    return RedirectResponse(authorization_url)

@router.get("/callback")
def auth_callback(request: Request, state: str, code: str, db: Session = Depends(get_session)):
    if state != request.session.get("state"):
        raise HTTPException(status_code=400, detail="State mismatch")

    redirect_uri = str(request.url_for("auth_callback"))

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state, redirect_uri=redirect_uri
    )

    # Restore the PKCE code verifier
    code_verifier = request.session.get("code_verifier")
    if code_verifier:
        setattr(flow, "code_verifier", code_verifier)

    flow.fetch_token(code=code)
    creds = flow.credentials

    # Use credentials to get user profile info from Google
    user_info_service = build('oauth2', 'v2', credentials=creds)
    user_info = user_info_service.userinfo().get().execute()

    email = user_info.get("email")
    name = user_info.get("name")
    picture = user_info.get("picture")

    # Save User to DB
    user = db.exec(select(User).where(User.email == email)).first()

    if not user:
        user = User(email=email, name=name, picture=picture)
        db.add(user)
        db.commit()
        db.refresh(user)

    # Save or update GoogleCredential
    db_cred = db.exec(select(GoogleCredential).where(GoogleCredential.user_id == user.id)).first()

    from datetime import timezone

    if not db_cred:
        db_cred = GoogleCredential(
            user_id=user.id,
            token=creds.token,
            refresh_token=creds.refresh_token,
            token_uri=creds.token_uri,
            client_id=creds.client_id,
            client_secret=creds.client_secret,
            scopes=",".join(creds.scopes) if creds.scopes else "",
            expiry=creds.expiry.replace(tzinfo=timezone.utc) if creds.expiry else None
        )
        db.add(db_cred)
    else:
        db_cred.token = creds.token
        if creds.refresh_token:
            db_cred.refresh_token = creds.refresh_token
        db_cred.expiry = creds.expiry.replace(tzinfo=timezone.utc) if creds.expiry else None
        db_cred.scopes = ",".join(creds.scopes) if creds.scopes else db_cred.scopes
        db.add(db_cred)

    db.commit()

    # Log the user into our app via session
    request.session["user_id"] = user.id

    return RedirectResponse(url="/")

@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")