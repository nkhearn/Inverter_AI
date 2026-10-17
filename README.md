# Edge Inverter AI Telemetry System (Text-to-SQL via MCP)

An edge-optimized Python application for natural language querying of inverter log telemetry databases. Designed to run efficiently on low-resource edge hardware (e.g., Raspberry Pi 5, mini PCs) using the **Model Context Protocol (MCP)** for database schema discovery and read-only SQL execution.

---

## Architecture & Features

```
+--------------------------+       +----------------------------+       +---------------------------+
|  Web UI (Browser)        |       |  FastAPI Backend Server    |       |  Local FastMCP Server     |
|  - HTML/CSS/JS           | ----> |  (Port 5115, 0.0.0.0)      | ----> |  (Port 8000, 0.0.0.0/mcp) |
|  - LocalStorage Keys     |       |  - LLM Orchestrator        |       |  - get_schema()           |
|  - Single-Page Interface |       |  - Multi-Provider Support  |       |  - execute_query() [SELECT|
+--------------------------+       +----------------------------+       +---------------------------+
                                                |                                    |
                                                v                                    v
                                   +--------------------------+       +-----------------------------+
                                   | Cloud LLM APIs           |       | Read-Only SQLite Database   |
                                   | - Google Gemini          |       | (`inverter_logs.db`)        |
                                   | - Groq / OpenRouter      |       +-----------------------------+
                                   +--------------------------+
```

### Key Highlights
1. **Model Context Protocol (MCP)**:
   - Uses `FastMCP` to expose read-only database tools (`get_schema` and `execute_query`).
   - Ensures strict SQL security by restricting operations exclusively to `SELECT` queries against `inverter_logs.db`.

2. **Edge-Optimized Design**:
   - Schema caching in memory to reduce token payload and network usage.
   - Enforces SQL aggregation (AVG, SUM, MIN, MAX) and strict `timestamp` filtering to keep response contexts small and fast.
   - Negligible local host RAM consumption (~50-80MB).

3. **Multi-Provider & Multi-Key Rotation**:
   - Primary support for **Google AI Studio (Gemini 2.0 Flash)** with 1,500 free requests/day.
   - Secondary fallback endpoints for **GroqCloud (Llama 3.3 70B)** and **OpenRouter (:free endpoints)**.
   - Support for client-side API key rotation across multiple projects/keys to multiply daily free quotas and bypass rate limits smoothly.
   - Mock/Demo mode for offline testing without API keys.

4. **Security & Browser LocalStorage**:
   - API keys and user credentials are stored exclusively in the user's browser `localStorage`.
   - Keys are transmitted directly in per-request headers to the orchestrator for processing and never stored on the server disk.

5. **Network Binding**:
   - Web application backend is bound to `0.0.0.0:5115`.
   - FastMCP server is bound to `0.0.0.0:8000`.

---

## Installation & Setup

### Prerequisites
- Python 3.10+
- `pip` package manager

### Quick Start
1. **Clone or Navigate to Project Directory**:
   ```bash
   cd /app
   ```

2. **Install Dependencies**:
   ```bash
   pip install fastmcp httpx fastapi uvicorn google-genai requests pydantic
   ```

3. **Generate Sample Telemetry Database** (if `inverter_logs.db` does not exist):
   ```bash
   python3 generate_sample_db.py
   ```
   *Generates 7 days of 1-minute inverter telemetry data (~10,080 rows).*

4. **Run the Application**:
   ```bash
   python3 main.py
   ```
   *The FastAPI web server automatically manages and launches the FastMCP server in the background if it is not already running.*

5. **Access the Web Interface**:
   Open your browser and navigate to:
   `http://<IP-ADDRESS>:5115` or `http://localhost:5115`

---

## Configuration & Settings

Navigate to the **Settings & Keys** tab in the web interface to configure:

| Setting | Description |
| :--- | :--- |
| **Primary LLM Provider** | Select between Google AI Studio, GroqCloud, OpenRouter, OpenAI, or Mock Engine. |
| **Google Gemini API Keys** | Input one or more Gemini API keys (one per line). Multi-key rotation automatically cycle keys on rate limits. |
| **Groq / OpenRouter Keys** | Input API keys for secondary providers. |
| **FastMCP Server URL** | Default: `http://127.0.0.1:8000/mcp`. Configures where the orchestrator reaches the MCP server. |

All settings are saved directly in your browser's `localStorage` and persist across sessions.

---

## Usage Examples

Ask natural language questions in the **Query Chat** interface:
- *"What was the average solar output and grid voltage over the past week?"*
- *"When did grid frequency drop below 49.5Hz or exceed 50.5Hz?"*
- *"Show battery state of charge when solar output exceeded 2kW."*
- *"What was the peak power output recorded yesterday?"*

---

## Project Structure

```
├── main.py                   # FastAPI Web Server entry point (Port 5115)
├── inv_mcp.py                # FastMCP Tool Server (Port 8000)
├── orchestrator.py           # Multi-provider LLM & MCP tool execution orchestrator
├── generate_sample_db.py     # Script to generate 1-minute telemetry sample SQLite DB
├── inverter_logs.db          # Inverter telemetry SQLite database
├── static/
│   ├── app.js                # Single-page frontend JavaScript
│   └── style.css             # Responsive dark-theme styling
├── templates/
│   └── index.html            # Web UI HTML template
└── README.md                 # System documentation
```

---

## Testing

Run unit & integration tests:
```bash
python3 -m unittest discover -s . -p "test_*.py"
```
