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
   - Support for dual authentication modes with Google Gemini: **API Key Credentials** and **Google OAuth 2.0 (User Credentials)**.
   - Secondary fallback endpoints for **GroqCloud (Llama 3.3 70B)**, **OpenRouter (:free endpoints)**, and **OpenAI (GPT-4o / GPT-4o-mini)**.
   - Client-side API key rotation across multiple projects/keys to multiply daily free quotas and bypass rate limits smoothly.
   - Mock/Demo mode for offline testing without API keys.

4. **Security & Browser LocalStorage**:
   - API keys, OAuth access tokens, and user credentials are stored exclusively in the user's browser `localStorage`.
   - Credentials are transmitted directly in per-request headers/payloads to the orchestrator for processing and are **never** stored on the server disk.

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
   python3 generate_sample_db.py --db-path /path/to/custom_inverter_logs.db
   ```
   *Generates 7 days of 1-minute inverter telemetry data (~10,080 rows). Default output path is `inverter_logs.db`.*

4. **Run the Application**:
   ```bash
   # Using default database location (inverter_logs.db):
   python3 main.py

   # Or specifying a custom database path via environment variable:
   INVERTER_DB_PATH=/path/to/custom_inverter_logs.db python3 main.py

   # Or starting the MCP server directly with a custom database path:
   python3 inv_mcp.py --db-path /path/to/custom_inverter_logs.db
   ```
   *The FastAPI web server automatically manages and launches the FastMCP server in the background if it is not already running.*

5. **Access the Web Interface**:
   Open your browser and navigate to:
   `http://<IP-ADDRESS>:5115` or `http://localhost:5115`

---

## Configuration & Settings

Navigate to the **Settings & Keys** tab in the web interface to configure options:

| Setting | Description |
| :--- | :--- |
| **Primary LLM Provider** | Select between Google AI Studio, GroqCloud, OpenRouter, OpenAI, or Mock Engine. |
| **Google Auth Method** | Choose between `Google API Key(s)` and `Google OAuth 2.0 (User Credentials)`. |
| **Google Gemini API Keys** | Input one or more Gemini API keys (one per line). Multi-key rotation automatically cycles keys on rate limits. |
| **Google OAuth Client ID** | (Optional for Browser Auth) Input your OAuth 2.0 Client ID from Google Cloud Console. |
| **Google OAuth Access Token** | OAuth 2.0 Bearer Token (auto-populated via browser Sign-in or entered manually). |
| **Secondary Provider Keys** | Input API keys for GroqCloud, OpenRouter, or OpenAI. |
| **FastMCP Server URL** | Default: `http://127.0.0.1:8000/mcp`. Configures where the orchestrator reaches the MCP server. |

### Database Path Configuration

The SQLite telemetry database location can be specified using any of the following methods (evaluated in order of precedence):

1. **Tool parameter**: Explicit `db_path` argument passed to FastMCP tools (`get_schema(db_path=...)`, `execute_query(sql_query=..., db_path=...)`).
2. **Environment variable**: `INVERTER_DB_PATH` or `DB_PATH` environment variables (e.g. `export INVERTER_DB_PATH=/var/data/inverter.db`).
3. **Command line argument**: `--db-path`, `--db`, or `-d` when running `inv_mcp.py` or `generate_sample_db.py` (e.g. `python3 inv_mcp.py --db-path /var/data/inverter.db`).
4. **Default fallback**: `inverter_logs.db` relative to the script directory.

All settings are saved directly in your browser's `localStorage` and persist across sessions.

---

## Authentication Instructions: Google Gemini

The system supports two methods for authenticating with Google AI / Gemini models: **API Key Credentials** and **Google OAuth 2.0 (User Credentials)**.

### Method 1: Google API Key Credentials (Recommended for Quick Setup)

Using API keys is the fastest way to get started with Google AI Studio.

1. **Obtain API Keys**:
   - Go to [Google AI Studio](https://aistudio.google.com/) and generate one or more API keys.
2. **Configure Web UI**:
   - Open the application and go to the **Settings & Keys** tab.
   - Set **Primary LLM Provider** to `Google AI Studio (Gemini 2.0 Flash)`.
   - Set **Google Auth Method** to `Google API Key(s)`.
   - Paste your API key(s) into the **Google Gemini API Keys** box (one key per line).
3. **Multi-Key Rotation**:
   - You can enter multiple Gemini API keys (one per line).
   - If a rate limit (`429 RESOURCE_EXHAUSTED`) is hit on one key, the LLM orchestrator automatically rotates to the next available key, effectively multiplying your daily free request quotas.
4. **Save Settings**:
   - Click **Save Settings to Browser Storage**.

---

### Method 2: Google OAuth 2.0 (User Credentials)

Google OAuth 2.0 allows you to authenticate using user credentials / OAuth bearer tokens instead of static API keys.

#### Option A: One-Click Browser Google Sign-In
1. **Create an OAuth Client ID**:
   - Open the [Google Cloud Console](https://console.cloud.google.com/).
   - Navigate to **APIs & Services > Credentials**.
   - Create an **OAuth 2.0 Client ID** with Application type set to **Web application**.
   - Under **Authorized JavaScript origins**, add your application's origin URL (e.g., `http://localhost:5115` or `http://<IP-ADDRESS>:5115`).
   - Enable the **Generative Language API** (`generativelanguage.googleapis.com`) in your Google Cloud project.
2. **Configure Web UI**:
   - Go to **Settings & Keys**.
   - Set **Primary LLM Provider** to `Google AI Studio (Gemini 2.0 Flash)`.
   - Set **Google Auth Method** to `Google OAuth 2.0 (User Credentials)`.
   - Paste your Google OAuth Client ID into the **Google OAuth Client ID** field.
3. **Sign In**:
   - Click the **🔑 Sign in with Google (Browser OAuth)** button.
   - Complete the Google authentication popup.
   - Upon successful sign-in, the **Google OAuth Access Token** field will automatically populate with a fresh OAuth bearer token.
4. **Save Settings**:
   - Click **Save Settings to Browser Storage**.

#### Option B: Manual Access Token Input
If you obtain a Google OAuth 2.0 access token via Google OAuth 2.0 Playground, `gcloud auth print-access-token`, or an external auth flow:

1. Go to **Settings & Keys**.
2. Set **Primary LLM Provider** to `Google AI Studio`.
3. Set **Google Auth Method** to `Google OAuth 2.0 (User Credentials)`.
4. Paste the bearer token (e.g., `ya29.a0A...`) directly into the **Google OAuth Access Token / User Credentials** field.
5. Click **Save Settings to Browser Storage**.

*Note: Google OAuth access tokens typically expire after 1 hour. Re-authenticate via the Sign in button or update the access token when expired.*

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
