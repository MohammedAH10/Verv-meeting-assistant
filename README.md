# Verv

Verv is a privacy-first AI meeting assistant that captures, transcribes, and summarizes meetings entirely on your infrastructure. Built by AI engineer passionate about data sovereignty and open source solutions. Perfect for enterprises that need advanced meeting intelligence without compromising on privacy, compliance, or control.

## Current State

This project is still in the foundation stage. The repository currently contains:

- a small Python entry point in `main.py`
- a FastAPI backend in `backend/app/main.py`
- a SQLite-backed database layer in `backend/app/db.py`
- transcript processing logic in `backend/app/transcript_processor.py`
- database schema validation in `backend/app/schema_validator.py`

## What Exists Today

- Meeting-related API models and endpoints are starting to take shape in the backend.
- Transcript processing is being built around chunking and model-driven summarization.
- Local persistence is handled through SQLite.
- The codebase is still being assembled, so this README will stay aligned with the repo as features land.

## Project Structure

- `main.py` - placeholder top-level entry point
- `backend/app/main.py` - FastAPI application and request models
- `backend/app/db.py` - database setup and storage helpers
- `backend/app/transcript_processor.py` - transcript chunking and summarization workflow
- `backend/app/schema_validator.py` - schema validation and migration checks
- `pyproject.toml` - Python project metadata and dependency configuration

## Notes

- This is a work in progress.
- Future documentation will be added as the UI, API surface, and workflow become more complete.
