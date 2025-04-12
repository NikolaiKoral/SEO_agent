import os
from typing import Dict, Any, TypedDict, Optional, List
import requests # Using requests directly as semrush-api-client might not be installed/configured

from a2a.tools import BaseTool

class SEMrushInput(TypedDict):
    keyword: str
    database: Optional[str] # e.g., 'us', 'dk'

class SEMrushTool(BaseTool):
    """Tool for retrieving data from SEMrush API"""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.api_key = self.config.get("SEMRUSH_API_KEY") or os.environ.get("SEMRUSH_API_KEY")
        self.base_url = "https://api.semrush.com"
    
    def _make_api_request(self, endpoint_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Helper function to make SEMrush API requests"""
        if not self.api_key:
            return {"error": "SEMrush API key not configured"}
            
        params["key"] = self.api_key
        
        try:
            # Construct the URL based on the endpoint type
            # Example: /analytics/v1/?type=phrase_this&...
            url = f"{self.base_url}/analytics/v1/" # Adjust if different endpoint needed
            
            response = requests.get(url, params=params)
            response.raise_for_status() # Raise an exception for bad status codes
            
            # SEMrush often returns CSV, need to parse it
            lines = response.text.strip().split('\n')
            if len(lines) < 2:
                return {"error": "No data returned from SEMrush API"}
                
            headers = [h.strip() for h in lines[0].split(';')]
            data_row = [d.strip() for d in lines[1].split(';')]
            
            if len(headers) != len(data_row):
                 return {"error": f"Mismatch between headers and data in SEMrush response. Headers: {headers}, Data: {data_row}"}

            return dict(zip(headers, data_row))
            
        except requests.exceptions.RequestException as e:
            return {"error": f"SEMrush API request failed: {e}"}
        except Exception as e:
            return {"error": f"Error processing SEMrush response: {e}"}

    async def invoke(self, args: SEMrushInput) -> Dict[str, Any]:
        """Invoke the SEMrush tool"""
        keyword = args.get("keyword")
        database = args.get("database", "us") # Default to US database
        
        if not keyword:
            return {"error": "Keyword is required"}
            
        # Get Keyword Overview data
        overview_params = {
            "type": "phrase_this",
            "phrase": keyword,
            "database": database,
            "export_columns": "Ph,Nq,Cp,Co,Nr,Td" # Keyword, Volume, CPC, Competition, Results, Trend
        }
        overview_data = self._make_api_request("phrase_this", overview_params)
        
        if "error" in overview_data:
            return overview_data # Return error if API call failed

        # Get Related Keywords (Example - adjust endpoint/params as needed)
        related_params = {
            "type": "phrase_related",
            "phrase": keyword,
            "database": database,
            "export_columns": "Ph,Nq", # Keyword, Volume
            "display_limit": 10
        }
        related_data_raw = self._make_api_request("phrase_related", related_params)
        
        # Process related keywords (assuming CSV format similar to overview)
        related_keywords = []
        if isinstance(related_data_raw, dict) and "error" not in related_data_raw:
             # This part needs refinement based on actual API response format for related keywords
             # For now, just storing the raw response if successful
             related_keywords = related_data_raw 
        elif isinstance(related_data_raw, dict) and "error" in related_data_raw:
             print(f"Warning: Could not fetch related keywords: {related_data_raw['error']}")


        # Combine results
        result = {
            "keyword": overview_data.get("Keyword"),
            "search_volume": int(overview_data.get("Search Volume", 0)),
            "cpc": float(overview_data.get("CPC (USD)", 0.0)), # Adjust currency if needed
            "competition": float(overview_data.get("Competition", 0.0)),
            "number_of_results": int(overview_data.get("Number of Results", 0)),
            "trend": [int(t) for t in overview_data.get("Trend", "").split(',')] if overview_data.get("Trend") else [],
            "related_keywords_raw": related_keywords # Store raw related data for now
            # Add more fields as needed by calling other SEMrush endpoints
        }
            
        return result
