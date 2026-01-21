"""
Vercel serverless function entry point for FastAPI app.
"""
import sys
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app

# Vercel Python runtime expects the app to be accessible as 'handler'
# For FastAPI, we can use the ASGI app directly
handler = app

