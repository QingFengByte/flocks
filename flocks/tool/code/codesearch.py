"""
CodeSearch Tool - Code context search

Searches for code examples, documentation, and API usage patterns.
Requires external API configuration.
"""

import json
from typing import Optional

from flocks.tool.registry import (
    ToolRegistry, ToolCategory, ToolParameter, ParameterType, ToolResult, ToolContext
)
from flocks.utils.log import Log


log = Log.create(service="tool.codesearch")


# API configuration
API_BASE_URL = "https://mcp.exa.ai"
DEFAULT_TOKENS = 5000
DEFAULT_TIMEOUT = 30  # seconds


DESCRIPTION = """Search for security examples, documentation, and API usage patterns.

Use this tool when you need:
- Security examples for a specific tool or framework
- API documentation and usage patterns
- Best practices for specific programming tasks
- Implementation references

Parameters:
- query: Search query (e.g., 'YARA malware detection rules', 'Suricata IDS signatures')
- tokensNum: Amount of context to return (1000-50000, default: 5000)

Tips:
- Be specific about the security tool/framework
- Include the security tool or technology if relevant
- Use higher tokensNum for comprehensive documentation"""


@ToolRegistry.register_function(
    name="codesearch",
    description=DESCRIPTION,
    category=ToolCategory.SEARCH,
    parameters=[
        ToolParameter(
            name="query",
            type=ParameterType.STRING,
            description="Search query for security context (e.g., 'YARA malware detection rules')",
            required=True
        ),
        ToolParameter(
            name="tokensNum",
            type=ParameterType.INTEGER,
            description="Number of tokens to return (1000-50000, default: 5000)",
            required=False,
            default=DEFAULT_TOKENS
        ),
    ]
)
async def codesearch_tool(
    ctx: ToolContext,
    query: str,
    tokensNum: int = DEFAULT_TOKENS,
) -> ToolResult:
    """
    Search for code context
    
    Args:
        ctx: Tool context
        query: Search query
        tokensNum: Amount of context tokens
        
    Returns:
        ToolResult with code context
    """
    if not query:
        return ToolResult(
            success=False,
            error="Search query is required"
        )
    
    # Validate tokensNum
    tokensNum = max(1000, min(50000, tokensNum))
    
    # Request permission
    await ctx.ask(
        permission="codesearch",
        patterns=[query],
        always=["*"],
        metadata={
            "query": query,
            "tokensNum": tokensNum
        }
    )
    
    title = f"Code search: {query}"
    
    try:
        import aiohttp
        
        # Build request
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "get_code_context_exa",
                "arguments": {
                    "query": query,
                    "tokensNum": tokensNum
                }
            }
        }
        
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE_URL}/mcp",
                json=request_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    return ToolResult(
                        success=False,
                        error=f"Code search error ({response.status}): {error_text}",
                        title=title
                    )
                
                response_text = await response.text()
                
                # Parse SSE response
                for line in response_text.split("\n"):
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data.get("result", {}).get("content"):
                            content = data["result"]["content"]
                            if content:
                                return ToolResult(
                                    success=True,
                                    output=content[0].get("text", ""),
                                    title=title,
                                    metadata={}
                                )
                
                return ToolResult(
                    success=True,
                    output="No code snippets or documentation found. Please try a different query, be more specific about the library or programming concept.",
                    title=title,
                    metadata={}
                )
                
    except ImportError:
        return ToolResult(
            success=False,
            error="Code search requires aiohttp library. Install with: pip install aiohttp",
            title=title
        )
    except Exception as e:
        if "timeout" in str(e).lower() or "abort" in str(e).lower():
            return ToolResult(
                success=False,
                error="Code search request timed out",
                title=title
            )
        
        return ToolResult(
            success=False,
            error=f"Code search failed: {str(e)}",
            title=title
        )
