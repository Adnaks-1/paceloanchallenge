"""
Vercel serverless function entry point for FastAPI app.
Vercel's @vercel/python can handle ASGI apps directly - just export 'app'.
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
    # Vercel's @vercel/python runtime can handle ASGI apps directly
    # Just export 'app' - no need for mangum or handler wrapper
except Exception as e:
    # If import fails, create a minimal error app
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        
        app = FastAPI(title="Error Handler")
        
        error_details = {
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
            "python_path": sys.path,
            "cwd": os.getcwd(),
            "vercel_env": os.getenv("VERCEL", "not set")
        }
        
        @app.get("/")
        async def error_root():
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Application initialization failed",
                    "details": error_details
                }
            )
        
        @app.get("/{path:path}")
        async def error_catchall(path: str):
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Application initialization failed",
                    "details": error_details,
                    "requested_path": path
                }
            )
    except Exception as fallback_error:
        # Last resort: create a minimal FastAPI app
        from fastapi import FastAPI
        app = FastAPI()
        
        @app.get("/{path:path}")
        async def critical_error(path: str):
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Critical initialization failure",
                    "init_error": str(e),
                    "fallback_error": str(fallback_error)
                }
            )

