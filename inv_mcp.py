import sqlite3
from pathlib import Path
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

# Define database path relative to this script
DB_PATH = Path(__file__).resolve().parent / "inverter_logs.db"

# Initialize the FastMCP server
mcp = FastMCP("Inverter Logs MCP Server")

def get_connection():
    """Establish a read-only connection to the SQLite database."""
    if not DB_PATH.exists():
        raise ToolError(f"Database not found at {DB_PATH}")
    # Open URI connection in read-only mode for safety
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

@mcp.tool()
def get_schema() -> str:
    """Retrieve the complete table schemas and indexes for inverter_logs.db."""
    conn = get_connection()
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
def execute_query(sql_query: str) -> list[dict]:
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

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        raise ToolError(f"SQL execution error: {str(e)}")
    finally:
        conn.close()

#if __name__ == "__main__":
#    mcp.run()

if __name__ == "__main__":
    # Start FastMCP using HTTP transport on a local port
    mcp.run(transport="http", host="0.0.0.0", port=8000)
