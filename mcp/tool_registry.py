"""Tool Registry for MCP Tools"""
from typing import Dict, Any, Callable
from dataclasses import dataclass

@dataclass
class ToolDefinition:
    """Tool definition structure"""
    name: str
    description: str
    parameters: Dict[str, Any]
    execute: Callable
    category: str = "general"

class ToolRegistry:
    """Registry for managing MCP tools"""
    
    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}
        self.categories = {
            "spatial": [],
            "statistical": [],
            "query": [],
            "comparison": [],
            "trajectory": []
        }
    
    def register_tool(self, tool_def: ToolDefinition):
        """Register a new tool"""
        self.tools[tool_def.name] = tool_def
        if tool_def.category in self.categories:
            self.categories[tool_def.category].append(tool_def.name)
    
    def get_tool(self, name: str) -> ToolDefinition:
        """Get tool by name"""
        return self.tools.get(name)
    
    def get_tools_by_category(self, category: str) -> list:
        """Get all tools in a category"""
        return [self.tools[name] for name in self.categories.get(category, [])]
    
    def get_all_tools(self) -> Dict[str, ToolDefinition]:
        """Get all registered tools"""
        return self.tools
    
    def get_tool_definitions_for_llm(self) -> list:
        """Get tool definitions formatted for LLM"""
        definitions = []
        for tool in self.tools.values():
            definitions.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "category": tool.category
            })
        return definitions