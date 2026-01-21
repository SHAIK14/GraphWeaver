"""
AgentNexus Main Application
FastAPI entry point for the multi-agent knowledge graph system.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import user_intent, file_suggestion
from app.core.config import get_settings


settings = get_settings()


app = FastAPI(
    title="AgentNexus - Knowledge Graph Builder",
    description="Multi-agent system for building knowledge graphs through conversation",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(user_intent.router)
app.include_router(file_suggestion.router)


@app.get("/")
async def root():
    """
    Root endpoint - basic health check.
    
    Returns:
        Welcome message with API info
    """
    return {
        "message": "Welcome to AgentNexus API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        Status of the API and its dependencies
    """
    # TODO: Add checks for OpenAI API, Neo4j connection
    return {
        "status": "healthy",
        "api": "operational",
        "agents": {
            "user_intent": "operational",
            "file_suggestion": "operational"
        }
    }


@app.get("/api/info")
async def api_info():
    """
    API information endpoint.
    
    Returns:
        Information about available agents and capabilities
    """
    return {
        "agents": {
            "user_intent": {
                "name": "User Intent Agent",
                "description": "Helps users define knowledge graph goals",
                "endpoint": "/api/user-intent/chat",
                "status": "operational"
            },
            "file_suggestion": {
                "name": "File Suggestion Agent",
                "description": "Suggests relevant files for knowledge graph import",
                "endpoint": "/api/file-suggestion/chat",
                "status": "operational"
            }
        },
        "features": [
            "Conversational graph ideation",
            "Multi-step workflows",
            "Session management",
            "Natural language processing"
        ]
    }


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Custom 404 handler"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": "The requested resource was not found",
            "path": str(request.url)
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Custom 500 handler"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "details": str(exc) if settings.openai_api_key else "Error details hidden in production"
        }
    )


if __name__ == "__main__":
    import uvicorn
    
   
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True  
    )
