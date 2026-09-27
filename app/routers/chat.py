from fastapi import APIRouter, Depends, Request, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from google import genai
from google.genai import types
import google.auth.transport.requests
from google.oauth2.credentials import Credentials as GoogleCredentialsObj

from app.database import get_session
from app.models import GoogleCredential, Conversation, Message
from app.tools import ClassroomTools
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
import traceback

load_dotenv()
router = APIRouter(prefix="/api/chat", tags=["chat"])

ai_client = genai.Client()

class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None

@router.post("/")
def chat_with_agent(payload: ChatRequest, request: Request, db: Session = Depends(get_session)):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # 1. Fetch User's Google Credentials
    db_cred = db.exec(select(GoogleCredential).where(GoogleCredential.user_id == user_id)).first()
    if not db_cred:
        raise HTTPException(status_code=401, detail="Google credentials not found")

    google_creds = GoogleCredentialsObj(
        token=db_cred.token, refresh_token=db_cred.refresh_token,
        token_uri=db_cred.token_uri, client_id=db_cred.client_id,
        client_secret=db_cred.client_secret
    )

    if google_creds.expired and google_creds.refresh_token:
        google_creds.refresh(google.auth.transport.requests.Request())
        db_cred.token = google_creds.token
        db_cred.expiry = google_creds.expiry.replace(tzinfo=timezone.utc) if google_creds.expiry else None
        db.add(db_cred)
        db.commit()

    # 2. Manage Conversation (Memory)
    if payload.conversation_id:
        conversation = db.get(Conversation, payload.conversation_id)
        if not conversation or conversation.user_id != user_id:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(user_id=user_id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # 3. Setup Tools
    tools_instance = ClassroomTools(google_creds)

    system_instruction = (
        "You are a helpful, friendly Google Classroom teaching assistant. "
        "You have tools to access the user's courses, assignments, announcements, students, and submissions. "
        "You can also create announcements. "
        "When the user asks you to do something complex, like reminding students who haven't submitted an assignment, "
        "use multiple tools in sequence! (e.g. get_students -> get_student_submissions -> create_announcement). "
        "Always summarize your actions nicely."
    )

    # Reconstruct history from database
    history = db.exec(select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at)).all()

    contents = []
    for msg in history:
        if msg.text:
            contents.append(types.Content(role=msg.role, parts=[types.Part.from_text(text=msg.text)]))

    # Save User's Message to Local DB
    user_msg = Message(conversation_id=conversation.id, role="user", text=payload.message)
    db.add(user_msg)
    db.commit()

    # 4. Call Gemini Chats API
    try:
        chat = ai_client.chats.create(
            model="gemini-3.5-flash-lite",
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=[
                    tools_instance.get_courses,
                    tools_instance.get_assignments,
                    tools_instance.get_announcements,
                    tools_instance.get_student_submissions,
                    tools_instance.get_students,
                    tools_instance.create_announcement
                ]
            ),
            history=contents
        )
        print(f"[AGENT] Sending message to Gemini: '{payload.message}'", flush=True)
        response = chat.send_message(payload.message)
        print(f"[AGENT] Received response from Gemini", flush=True)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    # 5. Save Model's Response to Local DB
    model_msg = Message(conversation_id=conversation.id, role="model", text=response.text)
    db.add(model_msg)
    db.commit()

    return {
        "conversation_id": conversation.id,
        "reply": response.text
    }
