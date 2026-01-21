"""
Vercel serverless function entry point for FastAPI app.
Uses mangum to convert ASGI app to AWS Lambda/API Gateway format for Vercel.
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

# Initialize error details as module-level variable
_init_error = None
_init_traceback = None

try:
    from app.main import app
    from mangum import Mangum
    
    # Wrap FastAPI ASGI app with Mangum for Vercel/AWS Lambda compatibility
    handler = Mangum(app, lifespan="off")
    
except Exception as e:
    # Store error for later use
    _init_error = e
    _init_traceback = traceback.format_exc()
    
    # Create a minimal error handler that will work even if imports fail
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        from mangum import Mangum
        
        error_app = FastAPI(title="Error Handler")
        
        @error_app.get("/")
        async def error_root():
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Application initialization failed",
                    "error_message": str(_init_error),
                    "error_type": type(_init_error).__name__,
                    "traceback": _init_traceback,
                    "python_path": sys.path,
                    "cwd": os.getcwd(),
                    "vercel_env": os.getenv("VERCEL", "not set")
                }
            )
        
        @error_app.get("/{path:path}")
        async def error_catchall(path: str):
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Application initialization failed",
                    "error_message": str(_init_error),
                    "error_type": type(_init_error).__name__,
                    "traceback": _init_traceback,
                    "requested_path": path,
                    "python_path": sys.path,
                    "cwd": os.getcwd()
                }
            )
        
        @error_app.get("/health")
        async def health():
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "error": "Application failed to initialize",
                    "details": str(_init_error)
                }
            )
        
        handler = Mangum(error_app, lifespan="off")
    except Exception as fallback_error:
        # If even FastAPI import fails, create a minimal handler
        def minimal_handler(event, context):
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": f'{{"error": "Critical initialization failure", "init_error": "{str(_init_error)}", "fallback_error": "{str(fallback_error)}", "traceback": "{_init_traceback}"}}'
            }
        
        handler = minimal_handler

