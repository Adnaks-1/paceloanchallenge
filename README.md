# Agentic Chatbot

A simple agentic chatbot built with FastAPI, LangGraph, LangChain, and Hugging Face.

## Architecture

```
FastAPI Server (localhost:8000)
       │
       ▼
LangGraph Agent ──▶ Hugging Face LLM
       │
       ▼
   skills.md (your instructions)
```

## Setup

### 1. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and add your Hugging Face API token:
- Get a free token at: https://huggingface.co/settings/tokens

### 4. Add your skills.md

Replace the placeholder `skills.md` with your own instructions file.

### 5. Run the server

```bash
uvicorn app.main:app --reload
```

Server will start at `http://localhost:8000`

## API Endpoints

### Chat
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!", "session_id": "my-session"}'
```

### Health Check
```bash
curl http://localhost:8000/health
```

### Clear Session
```bash
curl -X DELETE http://localhost:8000/session/my-session
```

### List Sessions
```bash
curl http://localhost:8000/sessions
```

## Interactive Docs

Visit `http://localhost:8000/docs` for Swagger UI documentation.

## Project Structure

```
paceloangroup/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app & endpoints
│   ├── agent.py             # LangGraph agent definition
│   ├── config.py            # Settings & env vars
│   └── session_store.py     # In-memory session management
├── skills.md                # Your instructions file
├── requirements.txt
├── .env.example
└── README.md
```

## Customization

### Change the LLM Model

Edit `.env`:
```
HF_MODEL=HuggingFaceH4/zephyr-7b-beta
```

### Modify Agent Behavior

Edit `skills.md` with your custom instructions, persona, and guidelines.




