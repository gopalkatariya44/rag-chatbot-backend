from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.api import auth, documents, chat, sessions, health
from app.db.session import init_db, init_db_vector
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db_vector()
    await init_db()
    yield
    # Shutdown
    pass

app = FastAPI(
    title=settings.PROJECT_NAME, 
    version=settings.VERSION,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://localhost:8080", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(documents.router, prefix=settings.API_V1_STR)
app.include_router(sessions.router, prefix=settings.API_V1_STR)
app.include_router(chat.router, prefix=settings.API_V1_STR)
app.include_router(health.router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    """
    Want to rander one html page in start
    """
    return FileResponse("app/static/index.html")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)