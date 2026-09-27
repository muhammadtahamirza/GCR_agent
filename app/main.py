import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

from app.database import create_db_and_tables
from app.routers import auth, classroom, chat

from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "super-secret-default-key")
)

app.include_router(auth.router)
app.include_router(classroom.router)
app.include_router(chat.router)

templates = Jinja2Templates(directory="app/templates")

from sqlmodel import Session
from fastapi import Depends
from app.database import get_session
from app.models import User

@app.get("/")
def read_root(request: Request, db: Session = Depends(get_session)):
    user_id = request.session.get("user_id")
    user = None
    if user_id:
        user = db.get(User, user_id)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request, "user_id": user_id, "user": user}
    )
