# Option Data Service

This project provides a Python-based service for pulling real-time option-chain data and storing it in PostgreSQL.

## Features
- FastAPI API for health checks, ingestion, and quote retrieval
- SQLAlchemy models for option quotes
- PostgreSQL persistence via Docker Compose
- Yahoo Finance provider as the initial real-time source

## Setup
1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Start PostgreSQL:
   ```bash
   docker compose up -d
   ```
3. Copy the environment file and adjust values if needed:
   ```bash
   copy .env.example .env
   ```
4. Run the API:
   ```bash
   python run.py
   ```

## Endpoints
- GET /health
- POST /ingest
- GET /quotes
