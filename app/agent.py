from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from openai import OpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from app.config import get_settings, load_skills
from app.session_store import session_store


class AgentState(TypedDict):
    """State schema for the agent graph."""
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str


def create_llm() -> OpenAI:
    """Create the OpenAI-compatible client for Hugging Face."""
    settings = get_settings()
    
    return OpenAI(
        base_url="https://router.huggingface.co/v1",
        api_key=settings.huggingface_api_token,
    )


def process_node(state: AgentState) -> AgentState:
    """Process the user message and generate a response."""
    client = create_llm()
    settings = get_settings()
    skills = load_skills()
    
    # Build the prompt with skills as system context
    system_message = SystemMessage(content=skills)
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
    ai_message = AIMessage(content=response_text.strip())
    
    # Save to session store
    session_store.add_message(state["session_id"], state["messages"][-1])  # Save user message
    session_store.add_message(state["session_id"], ai_message)  # Save AI response
    
    return {"messages": [ai_message], "session_id": state["session_id"]}


def format_messages_for_chat(messages: list[BaseMessage]) -> list[dict]:
    """Format messages into chat format for OpenAI-compatible API."""
    formatted = []
    
    for msg in messages:
        if isinstance(msg, SystemMessage):
            formatted.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            formatted.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            formatted.append({"role": "assistant", "content": msg.content})
    
    return formatted


def create_agent_graph() -> StateGraph:
    """Create and compile the LangGraph agent."""
    # Define the graph
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("process", process_node)
    
    # Add edges
    graph.add_edge(START, "process")
    graph.add_edge("process", END)

    # Compile and return
    return graph.compile()


# Create the agent instance
agent = create_agent_graph()


def chat(message: str, session_id: str) -> str:
    """
    Main chat function to interact with the agent.
    
    Args:
        message: User's input message
        session_id: Unique session identifier
        
    Returns:
        Agent's response string
    """
    # Get existing history
    history = session_store.get_history(session_id)
    
    # Create the user message
    user_message = HumanMessage(content=message)
    
    # Build initial state with history + new message
    initial_state: AgentState = {
        "messages": history + [user_message],
        "session_id": session_id,
    }
    
    # Run the agent
    result = agent.invoke(initial_state)
    
    # Extract and return the response
    final_message = result["messages"][-1]
    return final_message.content
