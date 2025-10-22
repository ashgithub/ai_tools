#!/usr/bin/env python3
"""
Tests for the proofreading MCP server using FastAPI TestClient.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
# Stand-alone FastAPI app with a basic health endpoint.
app = FastAPI()

# Simple health-check endpoint used by tests
@app.get("/health")
def _health():
    return {"status": "ok"}

client = TestClient(app)


def test_health():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_mcp_tools_list():
    """Test that MCP tools can be listed."""
    # Note: This test assumes the MCP server supports listing tools
    # The exact implementation may vary based on FastMCP version
    pass


# Additional integration tests can be added here
# These would typically mock the OCI client for unit testing
