"""
Configuration - load environment variables and app-wide settings for the MCP server.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SERVER_NAME: str = os.getenv("MCP_SERVER_NAME", "EDITH")
    MCP_SERVER_PORT: int = int(os.getenv("MCP_SERVER_PORT", 8000))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"


config = Config()
