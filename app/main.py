import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

from app.database import create_db_and_tables
from app.routers import auth, classroom

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

@app.get("/")
def read_root(request: Request):
    user_id = request.session.get("user_id")
    if user_id:
        return {"message": "You are logged in", "user_id": user_id, "courses_url": "/api/courses"}
    return {"message": "Please login", "login_url": "/auth/login"}
