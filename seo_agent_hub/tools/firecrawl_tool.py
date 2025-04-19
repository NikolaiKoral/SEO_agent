import os
from typing import Dict, Any, TypedDict, Optional, List, Union

# Need to handle potential import error if mcp-client is not installed
try:
    from mcp_client import MCPClient, McpError
    MCP_AVAILABLE = True
except ImportError:
    MCPClient = None
    McpError = None
    MCP_AVAILABLE = False

# A2A BaseTool import (assuming it's available in the environment)
try:
    from a2a.tools import BaseTool
except ImportError:
    # Define a dummy BaseTool if a2a is not available,
    # although the orchestrator check should prevent this tool from being used anyway.
    class BaseTool:
        def __init__(self, config=None): pass
        async def invoke(self, args: Dict[str, Any]) -> Dict[str, Any]:
            return {"error": "a2a package not found"}

# --- Define Input Schemas (mirroring MCP tool schemas) ---
# These could be more granular (one per tool) but a single large one might suffice for now

class FirecrawlLocation(TypedDict, total=False):
    country: str
    languages: List[str]

class FirecrawlAction(TypedDict, total=False):
    type: str # Literal["wait", "click", "screenshot", "write", "press", "scroll", "scrape", "executeJavascript"]
    selector: str
    milliseconds: int
    text: str
    key: str
    direction: str # Literal["up", "down"]
    script: str
    fullPage: bool

class FirecrawlExtractOptions(TypedDict, total=False):
    schema: Dict[str, Any]
    systemPrompt: str
    prompt: str

class FirecrawlScrapeOptions(TypedDict, total=False):
    formats: List[str] # Literal["markdown", "html", "rawHtml", "screenshot", "links", "screenshot@fullPage", "extract"]
    onlyMainContent: bool
    includeTags: List[str]
    excludeTags: List[str]
    waitFor: int
    timeout: int
    actions: List[FirecrawlAction]
    extract: FirecrawlExtractOptions
    mobile: bool
    skipTlsVerification: bool
    removeBase64Images: bool
    location: FirecrawlLocation

class FirecrawlMapOptions(TypedDict, total=False):
    search: str
    ignoreSitemap: bool
    sitemapOnly: bool
    includeSubdomains: bool
    limit: int

class FirecrawlCrawlWebhook(TypedDict, total=False):
    url: str
    headers: Dict[str, str]

class FirecrawlCrawlOptions(TypedDict, total=False):
    excludePaths: List[str]
    includePaths: List[str]
    maxDepth: int
    ignoreSitemap: bool
    limit: int
    allowBackwardLinks: bool
    allowExternalLinks: bool
    webhook: Union[str, FirecrawlCrawlWebhook]
    deduplicateSimilarURLs: bool
    ignoreQueryParameters: bool
    scrapeOptions: FirecrawlScrapeOptions # Re-use scrape options schema

class FirecrawlBatchScrapeOptions(TypedDict, total=False):
    # Subset of scrape options applicable to batch
    formats: List[str]
    onlyMainContent: bool
    includeTags: List[str]
    excludeTags: List[str]
    waitFor: int

class FirecrawlSearchOptions(TypedDict, total=False):
    limit: int
    lang: str
    country: str
    tbs: str
    filter: str
    location: FirecrawlLocation
    scrapeOptions: Dict[str, Any] # Simplified for search scrape

class FirecrawlExtractToolOptions(TypedDict, total=False):
    prompt: str
    systemPrompt: str
    schema: Dict[str, Any]
    allowExternalLinks: bool
    enableWebSearch: bool
    includeSubdomains: bool

class FirecrawlDeepResearchOptions(TypedDict, total=False):
    maxDepth: int
    timeLimit: int
    maxUrls: int

class FirecrawlGenerateLlmstxtOptions(TypedDict, total=False):
    maxUrls: int
    showFullText: bool

# --- Main Input TypedDict ---
class FirecrawlInput(TypedDict):
    action: str # Literal['scrape', 'map', 'crawl', 'batch_scrape', 'check_batch_status', 'check_crawl_status', 'search', 'extract', 'deep_research', 'generate_llmstxt']
    # Common parameters
    url: Optional[str]
    urls: Optional[List[str]]
    query: Optional[str]
    id: Optional[str] # For status checks
    # Action-specific options dictionaries
    scrape_options: Optional[FirecrawlScrapeOptions]
    map_options: Optional[FirecrawlMapOptions]
    crawl_options: Optional[FirecrawlCrawlOptions]
    batch_scrape_options: Optional[FirecrawlBatchScrapeOptions] # Note: MCP tool takes 'options'
    search_options: Optional[FirecrawlSearchOptions]
    extract_options: Optional[FirecrawlExtractToolOptions]
    deep_research_options: Optional[FirecrawlDeepResearchOptions]
    generate_llmstxt_options: Optional[FirecrawlGenerateLlmstxtOptions]


class FirecrawlTool(BaseTool):
    """
    Tool for interacting with the Firecrawl MCP server.
    Handles various Firecrawl actions like scraping, searching, crawling, and extracting data.
    """

    def __init__(self, config=None):
        self.config = config or {}
        # Allow overriding server name via config or env var
        self.mcp_server_name = self.config.get("FIRECRAWL_MCP_SERVER_NAME", "mcp-server-firecrawl")

        if not MCP_AVAILABLE:
            print("Warning: mcp-client package not found. Firecrawl tool will be disabled.")
            self.mcp_client = None
        else:
            try:
                # Initialize MCPClient. Assumes MCP server is running and configured.
                # Pass config if mcp-client supports it for auth/endpoint details
                self.mcp_client = MCPClient()
                print(f"FirecrawlTool initialized with MCP server: {self.mcp_server_name}")
            except Exception as e:
                 print(f"Warning: Failed to initialize MCPClient for Firecrawl: {e}")
                 self.mcp_client = None

    async def invoke(self, args: FirecrawlInput) -> Dict[str, Any]:
        """Invoke a Firecrawl MCP tool based on the specified action."""
        if not self.mcp_client:
            return {"error": "mcp-client package not installed or MCPClient failed to initialize"}

        action = args.get("action")
        if not action:
            return {"error": "Firecrawl 'action' is required in arguments"}

        # Map user-friendly action names to MCP tool names
        tool_map = {
            'scrape': 'firecrawl_scrape',
            'map': 'firecrawl_map',
            'crawl': 'firecrawl_crawl',
            'batch_scrape': 'firecrawl_batch_scrape',
            'check_batch_status': 'firecrawl_check_batch_status',
            'check_crawl_status': 'firecrawl_check_crawl_status',
            'search': 'firecrawl_search',
            'extract': 'firecrawl_extract',
            'deep_research': 'firecrawl_deep_research',
            'generate_llmstxt': 'firecrawl_generate_llmstxt',
        }

        tool_name = tool_map.get(action)
        if not tool_name:
            valid_actions = ", ".join(tool_map.keys())
            return {"error": f"Invalid Firecrawl action: '{action}'. Valid actions: {valid_actions}"}

        # Prepare arguments for the MCP tool call
        mcp_args = {}
        options = None # To hold the specific options dict

        try:
            # --- Argument validation and extraction based on action ---
            if action == 'scrape':
                if not args.get('url'): return {"error": "'url' is required for scrape action"}
                mcp_args['url'] = args['url']
                options = args.get('scrape_options', {})
            elif action == 'map':
                if not args.get('url'): return {"error": "'url' is required for map action"}
                mcp_args['url'] = args['url']
                options = args.get('map_options', {})
            elif action == 'crawl':
                if not args.get('url'): return {"error": "'url' is required for crawl action"}
                mcp_args['url'] = args['url']
                options = args.get('crawl_options', {})
            elif action == 'batch_scrape':
                if not args.get('urls'): return {"error": "'urls' is required for batch_scrape action"}
                mcp_args['urls'] = args['urls']
                # Note: MCP tool takes 'options', not 'batch_scrape_options'
                mcp_args['options'] = args.get('batch_scrape_options', {})
                options = None # Options are directly in mcp_args['options']
            elif action == 'check_batch_status':
                if not args.get('id'): return {"error": "'id' is required for check_batch_status action"}
                mcp_args['id'] = args['id']
            elif action == 'check_crawl_status':
                if not args.get('id'): return {"error": "'id' is required for check_crawl_status action"}
                mcp_args['id'] = args['id']
            elif action == 'search':
                if not args.get('query'): return {"error": "'query' is required for search action"}
                mcp_args['query'] = args['query']
                options = args.get('search_options', {})
            elif action == 'extract':
                if not args.get('urls'): return {"error": "'urls' is required for extract action"}
                mcp_args['urls'] = args['urls']
                options = args.get('extract_options', {}) # Pass all extract options
            elif action == 'deep_research':
                if not args.get('query'): return {"error": "'query' is required for deep_research action"}
                mcp_args['query'] = args['query']
                options = args.get('deep_research_options', {})
            elif action == 'generate_llmstxt':
                if not args.get('url'): return {"error": "'url' is required for generate_llmstxt action"}
                mcp_args['url'] = args['url']
                options = args.get('generate_llmstxt_options', {})

            # Add options to mcp_args if they exist (except for batch_scrape where it's handled differently)
            if options is not None:
                 mcp_args.update(options)

            # --- MCP Tool Call ---
            print(f"Calling Firecrawl MCP tool: {tool_name} with args: {mcp_args}") # Debug print
            result = await self.mcp_client.use_tool(
                server_name=self.mcp_server_name,
                tool_name=tool_name,
                arguments=mcp_args
            )

            # Check if the result itself indicates an error (some MCP tools might return errors in content)
            # This check might need refinement based on actual MCP server error formats
            if isinstance(result, dict) and result.get('isError'):
                 error_content = result.get('content', 'Unknown error content')
                 print(f"Error from Firecrawl tool '{tool_name}': {error_content}")
                 return {"error": f"Firecrawl tool '{tool_name}' returned an error: {error_content}"}
            elif isinstance(result, dict) and 'error' in result: # Another possible error format
                 print(f"Error from Firecrawl tool '{tool_name}': {result['error']}")
                 return {"error": f"Firecrawl tool '{tool_name}' returned an error: {result['error']}"}


            print(f"Firecrawl tool '{tool_name}' executed successfully.")
            return {"result": result} # Wrap successful result

        except McpError as e:
            print(f"MCP Error calling Firecrawl tool '{tool_name}': {e}")
            return {"error": f"MCP Error calling Firecrawl tool '{tool_name}': {e}"}
        except KeyError as e:
             print(f"Missing expected key in arguments for action '{action}': {e}")
             return {"error": f"Missing expected key in arguments for action '{action}': {e}"}
        except Exception as e:
            print(f"Unexpected error in FirecrawlTool invoke for action '{action}': {e}")
            # Consider logging the full traceback here for debugging
            import traceback
            traceback.print_exc()
            return {"error": f"Unexpected error calling Firecrawl tool '{tool_name}': {e}"}
