"""
Agent module with lazy imports for LangChain/LangGraph.
Heavy dependencies are only loaded when the chat endpoint is actually called.
"""
from typing import TypedDict, Annotated, Optional
from openai import OpenAI

from app.config import get_settings, load_skills
from app.session_store import session_store

# Lazy-loaded imports - only imported when chat() is called
_BaseMessage = None
_HumanMessage = None
_AIMessage = None
_SystemMessage = None
_StateGraph = None
_START = None
_END = None
_add_messages = None
_AgentState = None
_agent_instance: Optional[object] = None


def _lazy_import_langchain():
    """Lazy import LangChain and LangGraph modules only when needed."""
    global _BaseMessage, _HumanMessage, _AIMessage, _SystemMessage
    global _StateGraph, _START, _END, _add_messages, _AgentState
    
    if _BaseMessage is None:
        from langchain_core.messages import (
            BaseMessage, HumanMessage, AIMessage, SystemMessage
        )
        from langgraph.graph import StateGraph, START, END
        from langgraph.graph.message import add_messages
        
        _BaseMessage = BaseMessage
        _HumanMessage = HumanMessage
        _AIMessage = AIMessage
        _SystemMessage = SystemMessage
        _StateGraph = StateGraph
        _START = START
        _END = END
        _add_messages = add_messages


def _get_agent_state_type():
    """Get or create the AgentState TypedDict type."""
    global _AgentState
    
    if _AgentState is None:
        _lazy_import_langchain()
        
        class AgentState(TypedDict):
            """State schema for the agent graph."""
            messages: Annotated[list[_BaseMessage], _add_messages]
            session_id: str
        
        _AgentState = AgentState
    
    return _AgentState


def create_llm() -> OpenAI:
    """Create the OpenAI-compatible client for Hugging Face."""
    settings = get_settings()
    
    return OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=settings.huggingface_api_token,
    )


def process_node(state) -> dict:
    """Process the user message and generate a response."""
    _lazy_import_langchain()
    
    client = create_llm()
    settings = get_settings()
    skills = load_skills()
    
    # Build the prompt with skills as system context
    system_message = _SystemMessage(content=skills)
    messages = [system_message] + state["messages"]
    
    # Format messages for the chat API
    chat_messages = format_messages_for_chat(messages)
    
    # Generate response using chat completion
    response = client.chat.completions.create(
        model=settings.hf_model,
        messages=chat_messages,
        max_tokens=1024,
        temperature=0.6,
    )
    
    # Extract the response text
    response_text = response.choices[0].message.content
    
    # Create AI message from response
    ai_message = _AIMessage(content=response_text.strip())
    
    # Save to session store
    session_store.add_message(state["session_id"], state["messages"][-1])  # Save user message
    session_store.add_message(state["session_id"], ai_message)  # Save AI response
    
    return {"messages": [ai_message], "session_id": state["session_id"]}


def format_messages_for_chat(messages: list) -> list[dict]:
    """Format messages into chat format for OpenAI-compatible API."""
    _lazy_import_langchain()
    
    formatted = []
    
    for msg in messages:
        if isinstance(msg, _SystemMessage):
            formatted.append({"role": "system", "content": msg.content})
        elif isinstance(msg, _HumanMessage):
            formatted.append({"role": "user", "content": msg.content})
        elif isinstance(msg, _AIMessage):
            formatted.append({"role": "assistant", "content": msg.content})
    
    return formatted


def _get_agent():
    """Get or create the agent graph instance (lazy initialization)."""
    global _agent_instance
    
    if _agent_instance is None:
        _lazy_import_langchain()
        AgentState = _get_agent_state_type()
        
        # Create and compile the LangGraph agent
        graph = _StateGraph(AgentState)
        graph.add_node("process", process_node)
        graph.add_edge(_START, "process")
        graph.add_edge("process", _END)
        
        _agent_instance = graph.compile()
    
    return _agent_instance


def chat(message: str, session_id: str) -> str:
    """
    Main chat function to interact with the agent.
    Heavy dependencies are loaded lazily on first call.
    
    Args:
        message: User's input message
        session_id: Unique session identifier
        
    Returns:
        Agent's response string
    """
    _lazy_import_langchain()
    AgentState = _get_agent_state_type()
    agent = _get_agent()
    
    # Get existing history
    history = session_store.get_history(session_id)
    
    # Create the user message
    user_message = _HumanMessage(content=message)
    
    # Build initial state with history + new message
    initial_state = {
        "messages": history + [user_message],
        "session_id": session_id,
    }
    
    # Run the agent
    result = agent.invoke(initial_state)
    
    # Extract and return the response
    final_message = result["messages"][-1]
    return final_message.content
