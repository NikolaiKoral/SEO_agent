import json
import os
from typing import Dict, Any, List, Optional

# A2A imports (assuming they are installed)
try:
    from a2a.runners import LocalRunner # Or potentially another runner if needed
    from a2a.memory import SharedMemory
    from a2a.teams import Team
    from a2a.agents import Agent as A2AAgent # Alias to avoid conflict with our base Agent
    from a2a.tools import ToolRegistry
    A2A_AVAILABLE = True
except ImportError:
    print("Warning: google-a2a package not found. Orchestrator functionality will be limited.")
    A2A_AVAILABLE = False
    # Define dummy classes if A2A is not available to avoid runtime errors on import
    class LocalRunner: pass
    class SharedMemory: 
        def add(self, key, value): pass
        def get_all(self): return {}
    class Team: 
        @staticmethod
        def from_config(path, memory): return None
    class A2AAgent: pass
    class ToolRegistry:
        def __init__(self): self.tools = {}
        def register(self, tool_instance): 
             # Simple registration based on class name for placeholder
             self.tools[tool_instance.__class__.__name__] = tool_instance

# Local imports
from .shared_libraries.context_builder import ContextBuilder
# Import tool classes (adjust paths as needed)
from .tools.ga_connector_tool import GAConnectorTool
from .tools.search_console_tool import SearchConsoleTool
from .tools.merchant_center_tool import MerchantCenterTool
from .tools.semrush_tool import SEMrushTool
from .tools.google_trends_tool import GoogleTrendsTool
from .tools.firecrawl_tool import FirecrawlTool
# Add imports for other tools when implemented

class SEOOrchestrator:
    """Orchestrator for the SEO Analytics Agent Hub using A2A"""
    
    def __init__(self, config_path=None):
        """Initialize orchestrator"""
        if not A2A_AVAILABLE:
            raise ImportError("google-a2a package is required for the orchestrator.")
            
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize A2A components
        self.memory = SharedMemory()
        self.tool_registry = self._register_tools()
        self.runner = LocalRunner(tool_registry=self.tool_registry) # Pass registry to runner
        
        # Initialize teams (load from config files)
        self.data_collection_team = self._load_team("config/teams/data_collection_team.yaml")
        self.analysis_team = self._load_team("config/teams/analysis_team.yaml")
        
        # Initialize context builder
        self.context_builder = ContextBuilder()

    def _load_config(self, config_path):
        """Load configuration from file or environment variables"""
        config = {}
        # Load from environment first
        for key, value in os.environ.items():
            if key.startswith(('GA_', 'SEARCH_CONSOLE_', 'MERCHANT_CENTER_', 'SEMRUSH_', 'FIRECRAWL_', 'MCP_')): # Add other prefixes
                config[key] = value
        
        # Override with config file if provided
        if config_path and os.path.exists(config_path):
             try:
                 with open(config_path, 'r') as f:
                     file_config = json.load(f)
                     config.update(file_config) # File overrides environment
             except Exception as e:
                 print(f"Warning: Could not load config file {config_path}: {e}")

        print(f"Orchestrator configured with keys: {list(config.keys())}")
        return config

    def _register_tools(self) -> ToolRegistry:
        """Initialize and register all A2A tools"""
        registry = ToolRegistry()
        
        # Register each tool instance, passing the config
        registry.register(GAConnectorTool(self.config))
        registry.register(SearchConsoleTool(self.config))
        registry.register(MerchantCenterTool(self.config))
        registry.register(SEMrushTool(self.config))
        registry.register(GoogleTrendsTool(self.config))
        registry.register(FirecrawlTool(self.config))
        # Register other tools...
        
        print(f"Registered tools: {list(registry.tools.keys())}")
        return registry

    def _load_team(self, config_path: str) -> Optional[Team]:
        """Load an A2A team from its configuration file"""
        full_path = os.path.join(os.path.dirname(__file__), '..', config_path) # Adjust path relative to orchestrator.py
        if not os.path.exists(full_path):
             print(f"Warning: Team config file not found: {full_path}")
             return None
        try:
            # Pass shared memory and tool registry to the team
            return Team.from_config(full_path, memory=self.memory, tool_registry=self.tool_registry)
        except Exception as e:
            print(f"Error loading team from {full_path}: {e}")
            return None

    async def process_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a product using the agent teams"""
        print(f"\n--- Processing Product: {product_data.get('ean') or product_data.get('title')} ---")
        
        # Clear memory for the new product
        self.memory.clear() # Important to clear memory between product runs
        
        # Store initial product data in memory
        self.memory.add("initial_product_data", product_data)
        
        # Step 1: Run Data Collection Team
        if self.data_collection_team:
            print("Running Data Collection Team...")
            try:
                # The initial message can guide the team
                data_collection_task = f"Collect all available analytics and market data for the product: {json.dumps(product_data)}"
                # Run the team - A2A handles agent coordination within the team
                # The results will be stored in shared memory by the agents/tools
                await self.runner.run_team(self.data_collection_team, data_collection_task)
                print("Data Collection Team finished.")
            except Exception as e:
                print(f"Error running Data Collection Team: {e}")
        else:
            print("Data Collection Team not loaded.")

        # Step 2: Run Analysis Team
        if self.analysis_team:
            print("Running Analysis Team...")
            try:
                 # The analysis team uses the data collected in shared memory
                analysis_task = "Analyze all collected data in shared memory. Generate keyword insights, competitor analysis, and content optimization recommendations."
                await self.runner.run_team(self.analysis_team, analysis_task)
                print("Analysis Team finished.")
            except Exception as e:
                print(f"Error running Analysis Team: {e}")
        else:
             print("Analysis Team not loaded.")

        # Step 3: Build unified JSON context from memory
        print("Building final context...")
        # Retrieve all data stored in memory by the agents
        final_memory_state = self.memory.get_all() 
        unified_context = self.context_builder.build_context(
            product_data, # Pass original product data again for base structure
            final_memory_state 
        )
        
        print(f"--- Finished Processing Product: {product_data.get('ean') or product_data.get('title')} ---")
        return unified_context
