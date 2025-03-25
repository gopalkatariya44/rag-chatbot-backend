from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn
from app.api import auth, documents, chat, sessions
from app.db.session import init_db
    
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    pass

app = FastAPI(
    title="RAG Chatbot API", 
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(auth.router)
app.include_router(documents.router)

@app.get("/")
async def root():
    return {"message": "RAG Chatbot API"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)