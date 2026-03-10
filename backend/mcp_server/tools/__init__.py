"""Tool registration helpers for the private MCP server."""

from .projects import register_project_tools
from .workspace import register_workspace_tools

__all__ = ["register_project_tools", "register_workspace_tools"]
