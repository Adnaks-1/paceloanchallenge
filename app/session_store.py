from typing import Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


class SessionStore:
    """Simple in-memory session store for conversation history."""
    
    def __init__(self):
        self._sessions: dict[str, list[BaseMessage]] = {}
    
    def get_history(self, session_id: str) -> list[BaseMessage]:
        """Get conversation history for a session."""
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        return self._sessions[session_id]
    
    def add_message(self, session_id: str, message: BaseMessage) -> None:
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

