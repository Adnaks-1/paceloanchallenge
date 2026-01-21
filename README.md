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



