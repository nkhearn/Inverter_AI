import argparse
import os
import sys
import sqlite3
from pathlib import Path
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "inverter_logs.db"

def get_db_path(override_path: str | Path | None = None) -> Path:
    """Resolve the SQLite database path from explicit override parameter, env vars, CLI args, or default."""
    if override_path:
        return Path(override_path).resolve()

    # Check env vars
    env_path = os.getenv("INVERTER_DB_PATH") or os.getenv("DB_PATH")
    if env_path:
        return Path(env_path).resolve()

    # Check CLI arguments (--db-path, --db, -d)
    for i, arg in enumerate(sys.argv):
        if arg in ("--db-path", "--db", "-d") and i + 1 < len(sys.argv):
            return Path(sys.argv[i + 1]).resolve()
        elif arg.startswith("--db-path="):
            return Path(arg.split("=", 1)[1]).resolve()
        elif arg.startswith("--db="):
            return Path(arg.split("=", 1)[1]).resolve()

    return DEFAULT_DB_PATH.resolve()

# Initialize the FastMCP server
mcp = FastMCP("Inverter Logs MCP Server")

def get_connection(db_path: str | Path | None = None):
    """Establish a read-only connection to the SQLite database."""
    resolved_path = get_db_path(db_path)
    if not resolved_path.exists():
        raise ToolError(f"Database not found at {resolved_path}")
    # Open URI connection in read-only mode for safety
    conn = sqlite3.connect(f"file:{resolved_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

@mcp.tool()
def get_schema(db_path: str | None = None) -> str:
    """Retrieve the complete table schemas and indexes for the inverter logs database."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type IN ('table', 'index') AND sql IS NOT NULL;"
        )
        rows = cursor.fetchall()
        schema_sql = "\n".join([row["sql"] for row in rows])
        return schema_sql
    finally:
        conn.close()

@mcp.tool()
def execute_query(sql_query: str, db_path: str | None = None) -> list[dict]:
    """Execute a read-only SQL query against the inverter database.

    Guidelines for efficient usage:
    - Use aggregate functions (AVG, SUM, MIN, MAX) rather than selecting raw rows.
    - Always apply WHERE clauses on the 'timestamp' index for time-range filtering.
    - Limit large result sets.
    """
    cleaned_query = sql_query.strip().lower()

    # Enforce read-only safety check
    if not cleaned_query.startswith("select"):
        raise ToolError("Security restriction: Only read-only SELECT statements are allowed.")

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        raise ToolError(f"SQL execution error: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inverter Logs FastMCP Server")
    parser.add_argument("--db-path", "--db", "-d", dest="db_path", type=str, default=None, help="Path to SQLite database file")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    args, unknown = parser.parse_known_args()

    # Start FastMCP using HTTP transport
    mcp.run(transport="http", host=args.host, port=args.port)
