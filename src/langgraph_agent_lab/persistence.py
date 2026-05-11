"""Checkpointer adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver


def build_checkpointer(
    kind: str = "memory", database_url: str | None = None
) -> BaseCheckpointSaver | None:
    """Return a LangGraph checkpointer.

    Supports three modes:
    - "none": No persistence (stateless execution)
    - "memory": In-memory persistence (MemorySaver) - good for dev/testing
    - "sqlite": SQLite persistence with WAL mode - production-ready, survives restarts
    - "postgres": PostgreSQL persistence - for distributed systems
    
    SQLite implementation uses WAL (Write-Ahead Logging) mode for better concurrency
    and crash recovery. State survives process restarts when using same database file.
    """
    if kind == "none":
        return None
    
    if kind == "memory":
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
    
    if kind == "sqlite":
        import sqlite3
        
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "SQLite checkpointer requires: pip install langgraph-checkpoint-sqlite"
            ) from exc
        
        # Use provided database_url or default to checkpoints.db
        db_path = database_url or "checkpoints.db"
        
        # Create connection with proper settings
        # check_same_thread=False allows multi-threaded access
        conn = sqlite3.connect(db_path, check_same_thread=False)
        
        # Enable WAL (Write-Ahead Logging) mode for better concurrency and crash recovery
        # WAL mode allows readers and writers to operate concurrently
        conn.execute("PRAGMA journal_mode=WAL")
        
        # Create SqliteSaver with the connection
        # SqliteSaver will automatically create required tables on first use
        saver = SqliteSaver(conn=conn)
        
        # Setup tables (this is required for SqliteSaver to work)
        saver.setup()
        
        return saver
    
    if kind == "postgres":
        try:
            from langgraph.checkpoint.postgres import (
                PostgresSaver,  # type: ignore[import-not-found]
            )
        except ImportError as exc:
            raise RuntimeError(
                "Postgres checkpointer requires: pip install langgraph-checkpoint-postgres"
            ) from exc
        
        if not database_url:
            raise ValueError("Postgres checkpointer requires database_url parameter")
        
        return PostgresSaver.from_conn_string(database_url)
    
    raise ValueError(f"Unknown checkpointer kind: {kind}")
