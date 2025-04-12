import os
from typing import Dict, Any, TypedDict, Optional, List

from a2a.tools import BaseTool

# Need to handle potential import error if mcp-client is not installed
try:
    from mcp_client import MCPClient, McpError
except ImportError:
    MCPClient = None
    McpError = None

class FirecrawlInput(TypedDict):
    action: str # e.g., 'search', 'scrape', 'extract', 'deep_research'
    query: Optional[str] # For search, deep_research
    url: Optional[str] # For scrape, extract
    urls: Optional[List[str]] # For batch_scrape, extract
    limit: Optional[int] # For search
    scrapeOptions: Optional[Dict[str, Any]] # For search, crawl
    extractSchema: Optional[Dict[str, Any]] # For scrape, extract
    # Add other parameters as needed based on Firecrawl MCP tool schemas

class FirecrawlTool(BaseTool):
    """Tool for interacting with the Firecrawl MCP server"""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.mcp_server_name = "mcp-server-firecrawl" # Default name, can be configured
        if MCPClient is None:
            print("Warning: mcp-client package not found. Firecrawl tool will be disabled.")
            self.mcp_client = None
        else:
            try:
                # Initialize MCPClient. Assumes MCP server is running and configured.
                # Configuration might be needed depending on mcp-client setup
                self.mcp_client = MCPClient() 
            except Exception as e:
                 print(f"Warning: Failed to initialize MCPClient for Firecrawl: {e}")
                 self.mcp_client = None
    
    async def invoke(self, args: FirecrawlInput) -> Dict[str, Any]:
        """Invoke a Firecrawl MCP tool"""
        if not self.mcp_client:
            return {"error": "mcp-client package not installed or MCPClient failed to initialize"}
            
        action = args.get("action")
        if not action:
            return {"error": "Firecrawl action is required"}

        # Map action to Firecrawl MCP tool name
        tool_map = {
            'search': 'firecrawl_search',
            'scrape': 'firecrawl_scrape',
            'extract': 'firecrawl_extract', # Assuming extract is part of scrape or a separate tool
            'deep_research': 'firecrawl_deep_research',
            'batch_scrape': 'firecrawl_batch_scrape',
            'map': 'firecrawl_map',
            'crawl': 'firecrawl_crawl',
            # Add other mappings as needed
        }

        tool_name = tool_map.get(action)
        if not tool_name:
            return {"error": f"Invalid Firecrawl action: {action}. Valid actions: {list(tool_map.keys())}"}

        # Prepare arguments for the MCP tool call
        mcp_args = {}
        if action == 'search':
            if not args.get('query'): return {"error": "Query is required for search action"}
            mcp_args['query'] = args['query']
            if args.get('limit'): mcp_args['limit'] = args['limit']
            if args.get('scrapeOptions'): mcp_args['scrapeOptions'] = args['scrapeOptions']
        elif action == 'scrape':
            if not args.get('url'): return {"error": "URL is required for scrape action"}
            mcp_args['url'] = args['url']
            if args.get('formats'): mcp_args['formats'] = args['formats']
            if args.get('extractSchema'): 
                 mcp_args['formats'] = mcp_args.get('formats', []) + ['extract']
                 mcp_args['extract'] = {"schema": args['extractSchema']}
            # Add other scrape options...
        elif action == 'extract': # Assuming extract uses the scrape tool
             if not args.get('urls') and not args.get('url'): return {"error": "URL or URLs required for extract"}
             tool_name = 'firecrawl_scrape' # Use scrape tool for extraction
             if args.get('url'):
                 mcp_args['url'] = args['url']
             else: # Handle batch extraction if needed, might require firecrawl_batch_scrape
                 return {"error": "Batch extraction via 'extract' action not fully implemented yet. Use 'batch_scrape'."}
             mcp_args['formats'] = ['extract']
             if not args.get('extractSchema'): return {"error": "extractSchema is required for extract action"}
             mcp_args['extract'] = {"schema": args['extractSchema']}
        elif action == 'deep_research':
             if not args.get('query'): return {"error": "Query is required for deep_research action"}
             mcp_args['query'] = args['query']
             # Add other deep_research options...
        # Add argument handling for other actions (batch_scrape, map, crawl)

        try:
            # Use the MCP client to call the Firecrawl tool
            result = await self.mcp_client.use_tool(
                server_name=self.mcp_server_name,
                tool_name=tool_name,
                arguments=mcp_args
            )
            
            # Check if the result itself indicates an error (some MCP tools might return errors in content)
            if isinstance(result, dict) and result.get('isError'):
                 return {"error": f"Firecrawl tool '{tool_name}' returned an error: {result.get('content')}"}

            return {"result": result} # Wrap result for clarity

        except McpError as e:
            return {"error": f"MCP Error calling Firecrawl tool '{tool_name}': {e}"}
        except Exception as e:
            return {"error": f"Unexpected error calling Firecrawl tool '{tool_name}': {e}"}
