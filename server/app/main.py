from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routes.chat import router as chat_router


app = FastAPI(
    title = "graphweaver api",
    description = "api for graphweaver",
    version = "0.1.0",

)

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["http://localhost:3000", "http://localhost:5173"],
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"],
)

# Include routers
app.include_router(chat_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/")
def root():
    return {
        "message": "Welcome to graphweaver api",
        "docs": "/docs",
        "health": "/health"
    }



