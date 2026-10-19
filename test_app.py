import unittest
import asyncio
import subprocess
import time
from fastapi.testclient import TestClient

from main import app, ensure_mcp_server
from orchestrator import LLMOrchestrator
from fastmcp import Client

class TestInverterAISystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Start MCP server process
        cls.mcp_proc = subprocess.Popen(['python3', 'inv_mcp.py'])
        time.sleep(2)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if cls.mcp_proc and cls.mcp_proc.poll() is None:
            cls.mcp_proc.terminate()
            cls.mcp_proc.wait()

    def test_mcp_direct_tools(self):
        """Test FastMCP tools via fastmcp Client."""
        async def _test():
            async with Client('http://127.0.0.1:8000/mcp') as mcp_client:
                tools = await mcp_client.list_tools()
                tool_names = [t.name for t in tools]
                self.assertIn('get_schema', tool_names)
                self.assertIn('execute_query', tool_names)

                # Test get_schema
                schema_res = await mcp_client.call_tool('get_schema', {})
                self.assertIn('inverter_telemetry', schema_res.data)

                # Test execute_query
                query_res = await mcp_client.call_tool('execute_query', {'sql_query': 'SELECT COUNT(*) as count FROM inverter_telemetry;'})
                self.assertIsInstance(query_res.data, list)
                self.assertGreater(query_res.data[0]['count'], 0)

        asyncio.run(_test())

    def test_orchestrator_mock(self):
        """Test LLMOrchestrator mock execution."""
        orch = LLMOrchestrator('http://127.0.0.1:8000/mcp')
        res = orch.execute_with_llm(
            provider='mock',
            keys=[],
            user_prompt='What is the average grid voltage?'
        )
        self.assertIn('sql_query', res)
        self.assertIn('query_results', res)
        self.assertIn('summary', res)
        self.assertIsNone(res['error'])

    def test_google_oauth_missing_token_error(self):
        """Test error when Google OAuth mode is selected without access token."""
        orch = LLMOrchestrator('http://127.0.0.1:8000/mcp')
        with self.assertRaises(ValueError) as ctx:
            orch.execute_with_llm(
                provider='google',
                keys=[],
                user_prompt='Test prompt',
                auth_type='oauth',
                access_token=''
            )
        self.assertIn('access token is required', str(ctx.exception))

    def test_google_gemini_api_error_explanation(self):
        """Test Google Gemini API error handling and explanation when invalid key is provided."""
        orch = LLMOrchestrator('http://127.0.0.1:8000/mcp')
        with self.assertRaises(RuntimeError) as ctx:
            orch.execute_with_llm(
                provider='google',
                keys=['invalid_gemini_key_123'],
                user_prompt='What is the max grid voltage?'
            )
        self.assertIn('Google Gemini API Error', str(ctx.exception))

    def test_api_query_oauth_missing_token(self):
        """Test FastAPI /api/query endpoint with google provider and oauth auth_type without access token."""
        payload = {
            'prompt': 'Average solar output',
            'provider': 'google',
            'auth_type': 'oauth',
            'access_token': '',
            'api_keys': [],
            'mcp_url': 'http://127.0.0.1:8000/mcp'
        }
        response = self.client.post('/api/query', json=payload)
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn('access token is required', data['detail'])

    def test_mcp_security_restriction(self):
        """Test non-SELECT query restriction in execute_query tool."""
        async def _test():
            async with Client('http://127.0.0.1:8000/mcp') as mcp_client:
                try:
                    await mcp_client.call_tool('execute_query', {'sql_query': 'DROP TABLE inverter_telemetry;'})
                    self.fail("Should have raised error for non-SELECT statement")
                except Exception as e:
                    self.assertIn("Security restriction", str(e))

        asyncio.run(_test())

    def test_api_health_endpoint(self):
        """Test FastAPI /api/health endpoint."""
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['mcp_server'], 'running')

    def test_api_query_endpoint(self):
        """Test FastAPI /api/query endpoint with mock provider."""
        payload = {
            'prompt': 'Average solar output',
            'provider': 'mock',
            'api_keys': [],
            'mcp_url': 'http://127.0.0.1:8000/mcp'
        }
        response = self.client.post('/api/query', json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('summary', data)
        self.assertIn('sql_query', data)

    def test_web_ui_serving(self):
        """Test HTML and static file serving."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Inverter Telemetry AI Assistant', response.text)

        css_response = self.client.get('/static/style.css')
        self.assertEqual(css_response.status_code, 200)

        js_response = self.client.get('/static/app.js')
        self.assertEqual(js_response.status_code, 200)

    def test_configurable_db_path_mcp_tools(self):
        """Test tools using custom SQLite database path parameter and environment variables."""
        import tempfile
        import os
        from generate_sample_db import init_db
        from pathlib import Path
        from inv_mcp import get_schema, execute_query, get_db_path

        with tempfile.TemporaryDirectory() as tmpdir:
            custom_db = Path(tmpdir) / "custom_test.db"
            init_db(custom_db)

            # Test get_db_path override parameter
            self.assertEqual(get_db_path(custom_db), custom_db.resolve())

            # Test get_db_path via environment variable
            os.environ["INVERTER_DB_PATH"] = str(custom_db)
            try:
                self.assertEqual(get_db_path(), custom_db.resolve())
            finally:
                del os.environ["INVERTER_DB_PATH"]

            # Test direct tool call with db_path parameter
            schema = get_schema(db_path=str(custom_db))
            self.assertIn('inverter_telemetry', schema)

            results = execute_query("SELECT COUNT(*) as cnt FROM inverter_telemetry;", db_path=str(custom_db))
            self.assertIsInstance(results, list)
            self.assertGreater(results[0]['cnt'], 0)

if __name__ == '__main__':
    unittest.main()
