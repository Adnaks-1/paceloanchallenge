"""
Vercel serverless function entry point for FastAPI app.
Optimized for Vercel deployment with error handling.
"""
import sys
import os
import traceback
from pathlib import Path

# Add parent directory to path so we can import app modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set environment variables for Vercel
os.environ.setdefault("VERCEL", "1")

try:
    from app.main import app
    # Vercel Python runtime expects the app to be accessible as 'handler'
    # For FastAPI, we can use the ASGI app directly
    handler = app
except Exception as e:
    # Fallback error handler for deployment issues with detailed error info
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    error_app = FastAPI()
    
    # Capture full error details
    error_details = {
        "error": str(e),
        "error_type": type(e).__name__,
        "traceback": traceback.format_exc()
    }
    
    @error_app.get("/")
    async def error_root():
        return JSONResponse(
            status_code=500,
            content={
                "error": "Application initialization failed",
                "details": error_details
            }
        )
    
    @error_app.get("/{path:path}")
    async def error_catchall(path: str):
        return JSONResponse(
            status_code=500,
            content={
                "error": "Application initialization failed",
                "details": error_details,
                "requested_path": path
            }
        )
    
    @error_app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        return JSONResponse(
            status_code=500,
            content={
                "error": "Application initialization error",
                "details": error_details,
                "request_error": str(exc)
            }
        )
    
    handler = error_app

