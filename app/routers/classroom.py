from fastapi import APIRouter, Depends, Request, HTTPException
from sqlmodel import Session, select
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials as GoogleCredentialsObj
import google.auth.transport.requests

from app.database import get_session
from app.models import GoogleCredential

router = APIRouter(prefix="/api", tags=["classroom"])

@router.get("/courses")
def get_courses(request: Request, db: Session = Depends(get_session)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    db_cred = db.exec(select(GoogleCredential).where(GoogleCredential.user_id == user_id)).first()
    if not db_cred:
        raise HTTPException(status_code=401, detail="Google credentials not found")

    # Reconstruct google credentials
    creds = GoogleCredentialsObj(
        token=db_cred.token,
        refresh_token=db_cred.refresh_token,
        token_uri=db_cred.token_uri,
        client_id=db_cred.client_id,
        client_secret=db_cred.client_secret,
        scopes=db_cred.scopes.split(",") if db_cred.scopes else []
    )

    # Check if expired, refresh if necessary
    if creds.expired and creds.refresh_token:
        creds.refresh(google.auth.transport.requests.Request())
        db_cred.token = creds.token
        from datetime import timezone
        db_cred.expiry = creds.expiry.replace(tzinfo=timezone.utc) if creds.expiry else None
        db.add(db_cred)
        db.commit()

    try:
        service = build("classroom", "v1", credentials=creds)
        results = service.courses().list(pageSize=10).execute()
        courses = results.get("courses", [])
        return {"courses": courses}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
