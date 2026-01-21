"""
Session store with lazy imports for LangChain messages.
Messages are stored as generic objects to avoid eager loading.
"""
from typing import Optional, Any

# Lazy-loaded BaseMessage type
_BaseMessage = None


def _get_base_message_type():
    """Lazy import BaseMessage only when needed."""
    global _BaseMessage
    if _BaseMessage is None:
        from langchain_core.messages import BaseMessage
        _BaseMessage = BaseMessage
    return _BaseMessage


class SessionStore:
    """Simple in-memory session store for conversation history."""
    
    def __init__(self):
        # Store messages as Any to avoid eager import
        self._sessions: dict[str, list[Any]] = {}
    
    def get_history(self, session_id: str) -> list[Any]:
        """Get conversation history for a session."""
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        return self._sessions[session_id]
    
    def add_message(self, session_id: str, message: Any) -> None:
        """Add a message to session history."""
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append(message)
    
    def clear_session(self, session_id: str) -> None:
        """Clear a session's history."""
        if session_id in self._sessions:
            del self._sessions[session_id]
    
    def list_sessions(self) -> list[str]:
        """List all active session IDs."""
        return list(self._sessions.keys())


# Global session store instance
session_store = SessionStore()

