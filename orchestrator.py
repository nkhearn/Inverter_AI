import sys
import time
import json
import asyncio
import httpx
from typing import List, Dict, Any, Optional
from itertools import cycle
from fastmcp import Client

class LLMOrchestrator:
    """
    Edge-optimized LLM Orchestrator supporting Google Gemini, Groq, OpenRouter,
    and generic OpenAI-compatible APIs. Features multi-key rotation, retry/backoff,
    and schema caching. Utilizes official FastMCP Client over Streamlined SSE/HTTP.
    """

    def __init__(self, mcp_server_url: str = "http://127.0.0.1:8000/mcp"):
        # Ensure url ends with /mcp endpoint if port 8000 specified without path
        if not mcp_server_url.endswith("/mcp"):
            self.mcp_server_url = f"{mcp_server_url.rstrip('/')}/mcp"
        else:
            self.mcp_server_url = mcp_server_url

        self._cached_schema: Optional[str] = None

    def call_mcp_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Call a FastMCP tool via fastmcp Client asynchronously."""
        async def _call():
            async with Client(self.mcp_server_url) as client:
                res = await client.call_tool(tool_name, arguments or {})
                return res.data

        return asyncio.run(_call())

    def get_schema(self, force_refresh: bool = False) -> str:
        """Fetch and cache DB schema to minimize context overhead."""
        if not self._cached_schema or force_refresh:
            self._cached_schema = str(self.call_mcp_tool("get_schema"))
        return self._cached_schema

    def _rotate_keys(self, keys: List[str]):
        """Generator yielding API keys in rotation."""
        if not keys:
            yield None
        else:
            for k in cycle(keys):
                yield k

    def execute_with_llm(
        self,
        provider: str,
        keys: List[str],
        user_prompt: str,
        model_name: Optional[str] = None,
        auth_type: str = "api_key",
        access_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main execution flow:
        1. Fetch schema from FastMCP.
        2. Prompt LLM to generate SQL based on prompt & schema.
        3. Execute SQL via FastMCP `execute_query`.
        4. Prompt LLM to synthesize final plain-language answer.
        """
        schema_info = self.get_schema()

        system_instruction = (
            "You are an expert SQL assistant for inverter log telemetry.\n"
            "Guidelines:\n"
            "- Output ONLY valid raw SQL inside ```sql ... ``` code blocks.\n"
            "- Use aggregate functions (AVG, SUM, MIN, MAX, COUNT) rather than selecting raw rows when appropriate.\n"
            "- Always apply WHERE clauses on 'timestamp' for time filtering when relevant.\n"
            "- Frequency anomaly logic: ac_input_freq < 49.5 OR ac_input_freq > 50.5.\n"
        )

        sql_generation_prompt = (
            f"Database Schema:\n{schema_info}\n\n"
            f"User Question: {user_prompt}\n"
            "Generate the SQL query to answer the question."
        )

        # Step 1: Generate SQL query using chosen provider
        sql_response_text = self._query_llm_provider(
            provider=provider,
            keys=keys,
            system_instruction=system_instruction,
            prompt=sql_generation_prompt,
            model_name=model_name,
            auth_type=auth_type,
            access_token=access_token
        )

        # Extract SQL string
        sql_query = sql_response_text.strip()
        if "```sql" in sql_query:
            sql_query = sql_query.split("```sql")[1].split("```")[0].strip()
        elif "```" in sql_query:
            sql_query = sql_query.split("```")[1].split("```")[0].strip()

        # Step 2: Execute SQL via FastMCP
        execution_error = None
        query_results = []
        try:
            query_results = self.call_mcp_tool("execute_query", {"sql_query": sql_query})
        except Exception as e:
            execution_error = str(e)

        # Step 3: Synthesize plain-language answer
        if execution_error:
            synthesis_prompt = (
                f"User Question: {user_prompt}\n"
                f"Attempted SQL: {sql_query}\n"
                f"SQL Error: {execution_error}\n"
                "Explain the error clearly to the user and suggest how they might rephrase or solve it."
            )
        else:
            # Truncate query results if huge to protect RAM/tokens
            results_str = json.dumps(query_results[:50], indent=2)
            if len(query_results) > 50:
                results_str += f"\n... [{len(query_results) - 50} more rows truncated]"

            synthesis_prompt = (
                f"User Question: {user_prompt}\n"
                f"Executed SQL: {sql_query}\n"
                f"Query Results:\n{results_str}\n\n"
                "Provide a concise, clear summary answering the user's question directly based on these results."
            )

        summary_response_text = self._query_llm_provider(
            provider=provider,
            keys=keys,
            system_instruction="You are a helpful telemetry analyst explaining database results clearly.",
            prompt=synthesis_prompt,
            model_name=model_name,
            auth_type=auth_type,
            access_token=access_token
        )

        return {
            "prompt": user_prompt,
            "sql_query": sql_query,
            "query_results": query_results,
            "summary": summary_response_text,
            "error": execution_error,
            "provider_used": provider
        }

    def _query_llm_provider(
        self,
        provider: str,
        keys: List[str],
        system_instruction: str,
        prompt: str,
        model_name: Optional[str] = None,
        auth_type: str = "api_key",
        access_token: Optional[str] = None
    ) -> str:
        """Query LLM with retries, backoff, and key rotation."""
        if provider == "google" and auth_type == "oauth":
            if not access_token or not access_token.strip():
                raise ValueError("Google OAuth access token is required when using OAuth authentication mode.")
            return self._call_google_gemini_oauth(
                access_token=access_token,
                system_instruction=system_instruction,
                prompt=prompt,
                model=model_name or "gemini-2.0-flash"
            )

        if not keys and provider not in ("mock", "local"):
            raise ValueError(f"No API key provided for provider '{provider}'. Please configure keys in Settings.")

        key_pool = self._rotate_keys(keys)
        retries = max(len(keys) * 2, 3) if keys else 1

        last_exception = None
        for attempt in range(retries):
            current_key = next(key_pool) if keys else None
            try:
                if provider == "google":
                    return self._call_google_gemini(
                        api_key=current_key,
                        system_instruction=system_instruction,
                        prompt=prompt,
                        model=model_name or "gemini-2.0-flash"
                    )
                elif provider in ("groq", "openrouter", "openai"):
                    return self._call_openai_compatible(
                        provider=provider,
                        api_key=current_key,
                        system_instruction=system_instruction,
                        prompt=prompt,
                        model=model_name
                    )
                elif provider == "mock":
                    if "Database Schema" in prompt:
                        return "```sql\nSELECT COUNT(*) as total_records, AVG(grid_voltage) as avg_grid_volts FROM inverter_telemetry;\n```"
                    return "The inverter telemetry database currently contains data with average stable grid voltage operating as expected."
                else:
                    raise ValueError(f"Unsupported provider: {provider}")
            except Exception as e:
                last_exception = e
                err_msg = str(e)
                print(f"[LLMOrchestrator] Provider '{provider}' attempt {attempt + 1}/{retries} failed: {err_msg}", file=sys.stderr, flush=True)
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "rate_limit" in err_msg.lower():
                    time.sleep((2 ** attempt) + 0.5)
                else:
                    time.sleep(0.5)

        raise RuntimeError(f"Failed to query provider '{provider}' after {retries} attempts. Last error: {last_exception}")

    def _call_google_gemini(self, api_key: str, system_instruction: str, prompt: str, model: str) -> str:
        """Google GenAI API call using API Key."""
        from google import genai
        from google.genai import types, errors

        try:
            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2
            )
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )

            text = None
            try:
                text = response.text
            except (AttributeError, ValueError):
                pass

            if text:
                return text

            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                finish_reason = getattr(candidate, "finish_reason", None)
                safety_ratings = getattr(candidate, "safety_ratings", None)
                raise RuntimeError(
                    f"Gemini API returned response with no text. Finish reason: {finish_reason}. "
                    f"Safety ratings: {safety_ratings}"
                )
            raise RuntimeError(f"Gemini API returned an empty response format: {response}")

        except errors.APIError as e:
            raise RuntimeError(f"Google Gemini API Error (code {e.code}): {e.message}") from e
        except Exception as e:
            if "google" in type(e).__module__:
                raise RuntimeError(f"Google Gemini API Request Error: {e}") from e
            raise

    def _call_google_gemini_oauth(self, access_token: str, system_instruction: str, prompt: str, model: str) -> str:
        """Google GenAI API call using OAuth 2.0 User Credentials / Access Token."""
        # Clean model name if necessary
        model_name = model.replace("models/", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"

        headers = {
            "Authorization": f"Bearer {access_token.strip()}",
            "Content-Type": "application/json"
        }

        payload = {
            "system_instruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2
            }
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                err_detail = resp.text
                try:
                    err_json = resp.json()
                    if "error" in err_json and "message" in err_json["error"]:
                        err_detail = err_json["error"]["message"]
                except Exception:
                    pass
                raise RuntimeError(f"Google Gemini OAuth API Error ({resp.status_code}): {err_detail}")

            data = resp.json()
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as e:
                raise RuntimeError(f"Unexpected Google Gemini API response format: {data}") from e

    def _call_openai_compatible(
        self,
        provider: str,
        api_key: str,
        system_instruction: str,
        prompt: str,
        model: Optional[str]
    ) -> str:
        """Generic OpenAI-compatible API call (Groq, OpenRouter, OpenAI)."""
        base_urls = {
            "groq": "https://api.groq.com/openai/v1/chat/completions",
            "openrouter": "https://openrouter.ai/api/v1/chat/completions",
            "openai": "https://api.openai.com/v1/chat/completions"
        }
        default_models = {
            "groq": "llama-3.3-70b-versatile",
            "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
            "openai": "gpt-4o-mini"
        }

        url = base_urls[provider]
        selected_model = model or default_models[provider]

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
