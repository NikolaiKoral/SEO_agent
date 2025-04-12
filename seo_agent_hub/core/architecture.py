from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class Agent(ABC):
    """Base class for all agents"""
    
    @abstractmethod
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input data and return results"""
        pass

class DataCollectionAgent(Agent):
    """Base class for agents that collect data from external sources"""
    
    @abstractmethod
    def get_source_name(self) -> str:
        """Return the name of the data source"""
        pass
    
    @abstractmethod
    def check_credentials(self) -> bool:
        """Check if the required credentials are available"""
        pass

class AnalysisAgent(Agent):
    """Base class for agents that analyze data"""
    
    @abstractmethod
    def get_analysis_type(self) -> str:
        """Return the type of analysis performed"""
        pass
    
    @abstractmethod
    def get_required_sources(self) -> List[str]:
        """Return a list of required data sources"""
        pass

class Orchestrator:
    """Coordinates the activity of all agents"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.data_collection_agents = {}
        self.analysis_agents = {}
    
    def register_data_collection_agent(self, agent: DataCollectionAgent) -> None:
        """Register a data collection agent"""
        if agent.check_credentials():
            self.data_collection_agents[agent.get_source_name()] = agent
    
    def register_analysis_agent(self, agent: AnalysisAgent) -> None:
        """Register an analysis agent"""
        self.analysis_agents[agent.get_analysis_type()] = agent
    
    def process_product(self, product_data: Dict[str, Any], enabled_sources: Optional[List[str]] = None) -> Dict[str, Any]:
        """Process a product using all registered agents"""
        # Collect all data
        collected_data = {}
        sources_to_use = enabled_sources or list(self.data_collection_agents.keys())
        
        for source_name in sources_to_use:
            if source_name in self.data_collection_agents:
                try:
                    agent = self.data_collection_agents[source_name]
                    collected_data[source_name] = agent.process(product_data)
                except Exception as e:
                    print(f"Error collecting data from {source_name}: {e}")
        
        # Analyze collected data
        analysis_results = {}
        for analysis_type, agent in self.analysis_agents.items():
            required_sources = agent.get_required_sources()
            if all(source in collected_data for source in required_sources):
                try:
                    # Create input for analysis agent
                    analysis_input = {
                        "product_data": product_data,
                        **{source: collected_data[source] for source in required_sources}
                    }
                    
                    # Run analysis
                    analysis_results[analysis_type] = agent.process(analysis_input)
                except Exception as e:
                    print(f"Error in {analysis_type} analysis: {e}")
        
        # Create unified context
        unified_context = {
            "product_data": product_data,
            "collected_data": collected_data,
            "analysis_results": analysis_results,
            "enabled_sources": sources_to_use
        }
        
        return unified_context
