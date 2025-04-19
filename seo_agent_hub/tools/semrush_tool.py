import os
import logging # Added import
from typing import Dict, Any, TypedDict, Optional, List
import requests # Using requests directly as semrush-api-client might not be installed/configured

# A2A BaseTool import (assuming it's available in the environment)
try:
    from a2a.tools import BaseTool
except ImportError:
    class BaseTool:
        def __init__(self, config=None): pass
        async def invoke(self, args: Dict[str, Any]) -> Dict[str, Any]:
            return {"error": "a2a package not found"}

# Setup logging
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class SEMrushInput(TypedDict):
    keyword: str
    database: Optional[str] # e.g., 'us', 'dk'
    # Add other potential inputs like 'target_url' if needed for other endpoints

class SEMrushTool(BaseTool):
    """Tool for retrieving data from SEMrush API"""

    def __init__(self, config=None):
        # Configuration now primarily relies on environment variables
        # self.config = config or {} # config parameter is no longer used for these core settings
        self.api_key = os.environ.get("SEMRUSH_API_KEY")
        self.base_url = os.environ.get("SEMRUSH_BASE_URL", "https://api.semrush.com") # Use env var or default
        if self.api_key:
            logger.info(f"SEMrushTool initialized with API key, using base URL: {self.base_url}")
        else:
            logger.error("SEMrush API key (SEMRUSH_API_KEY) not found in config or environment.")

    def _parse_semrush_csv(self, csv_text: str) -> List[Dict[str, str]]:
        """Parses SEMrush semicolon-separated CSV text into a list of dictionaries."""
        lines = csv_text.strip().split('\n')
        if len(lines) < 2:
            logger.warning("SEMrush response has less than 2 lines (header + data).")
            return [] # Return empty list if no data rows

        headers = [h.strip().lower().replace(' ', '_') for h in lines[0].split(';')] # Normalize headers
        parsed_data = []

        for i, line in enumerate(lines[1:]): # Iterate through data rows
            data_row = [d.strip() for d in line.split(';')]
            if len(headers) != len(data_row):
                logger.warning(f"Row {i+1}: Mismatch between headers ({len(headers)}) and data ({len(data_row)}). Skipping row. Headers: {headers}, Data: {data_row}")
                continue # Skip rows with mismatch
            parsed_data.append(dict(zip(headers, data_row)))

        return parsed_data

    def _make_api_request(self, endpoint_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Helper function to make SEMrush API requests and parse the response."""
        if not self.api_key:
            logger.error("SEMrush API key not configured.")
            return {"error": "SEMrush API key not configured"}

        params["key"] = self.api_key
        # Ensure 'type' is included for analytics endpoint
        if 'type' not in params:
            params['type'] = endpoint_type # Use endpoint_type if 'type' param is missing

        # Construct the URL based on the endpoint type
        # Assuming analytics/v1/ for now, adjust if other endpoints are used
        url = f"{self.base_url}/analytics/v1/"
        logger.debug(f"Making SEMrush API request to {url} with params: {params}")

        try:
            response = requests.get(url, params=params, timeout=30) # Added timeout
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

            logger.debug(f"SEMrush API request successful (Status: {response.status_code}). Response text length: {len(response.text)}")

            # Check for explicit error messages in the response text (SEMrush format varies)
            if "ERROR" in response.text[:100]: # Check beginning of response for common error patterns
                 logger.error(f"SEMrush API returned an error message: {response.text}")
                 # Attempt to extract a cleaner error message if possible
                 error_match = response.text.split("::")
                 clean_error = error_match[1].strip() if len(error_match) > 1 else response.text
                 return {"error": f"SEMrush API error: {clean_error}"}

            # Parse the CSV response
            parsed_data = self._parse_semrush_csv(response.text)

            if not parsed_data:
                 logger.warning(f"No data parsed from SEMrush response for endpoint {endpoint_type}, params {params}.")
                 # Return empty list or specific message instead of error? Depends on expected behavior.
                 # For now, returning an empty list within a 'data' key for consistency.
                 return {"data": []}

            # SEMrush often returns single row for phrase_this, list for others
            # Return the first item if it was likely a single-row response, else the list
            if endpoint_type == "phrase_this" and len(parsed_data) == 1:
                return parsed_data[0]
            else:
                return {"data": parsed_data} # Wrap list results in a 'data' key

        except requests.exceptions.Timeout:
            logger.error(f"SEMrush API request timed out for endpoint {endpoint_type}.")
            return {"error": "SEMrush API request timed out"}
        except requests.exceptions.HTTPError as e:
            logger.error(f"SEMrush API request failed with HTTP status {e.response.status_code}. Response: {e.response.text}")
            return {"error": f"SEMrush API HTTP error: {e.response.status_code} - {e.response.reason}"}
        except requests.exceptions.RequestException as e:
            logger.exception(f"SEMrush API request failed: {e}")
            return {"error": f"SEMrush API request failed: {e}"}
        except Exception as e:
            logger.exception(f"Error processing SEMrush response for endpoint {endpoint_type}: {e}")
            return {"error": f"Error processing SEMrush response: {e}"}

    async def invoke(self, args: SEMrushInput) -> Dict[str, Any]:
        """Invoke the SEMrush tool to get keyword overview and related keywords."""
        logger.info(f"Invoking SEMrushTool with args: {args}")
        keyword = args.get("keyword")
        database = args.get("database", "us") # Default to US database

        if not keyword:
            logger.error("Missing required argument: keyword")
            return {"error": "Keyword is required"}
        if not self.api_key:
             logger.error("SEMrush API key not configured, cannot invoke tool.")
             return {"error": "SEMrush API key not configured"}

        # --- Get Keyword Overview data ---
        overview_params = {
            "type": "phrase_this",
            "phrase": keyword,
            "database": database,
            "export_columns": "Ph,Nq,Cp,Co,Nr,Td" # Keyword, Volume, CPC, Competition, Results, Trend
        }
        logger.info(f"Fetching SEMrush keyword overview for '{keyword}' in db '{database}'")
        overview_data = self._make_api_request("phrase_this", overview_params)

        if "error" in overview_data:
            logger.error(f"Failed to get keyword overview: {overview_data['error']}")
            # Return only the error, or continue to try related? For now, return error.
            return {"error": f"Failed to get SEMrush keyword overview: {overview_data['error']}"}

        # --- Get Related Keywords ---
        related_params = {
            "type": "phrase_related",
            "phrase": keyword,
            "database": database,
            "export_columns": "Ph,Nq,Rl", # Keyword, Volume, Relevance
            "display_limit": 10 # Get top 10 related
        }
        logger.info(f"Fetching SEMrush related keywords for '{keyword}' in db '{database}'")
        related_data_result = self._make_api_request("phrase_related", related_params)

        related_keywords_processed = []
        related_error = None
        if "error" in related_data_result:
            related_error = f"Failed to get SEMrush related keywords: {related_data_result['error']}"
            logger.warning(related_error)
        elif "data" in related_data_result and isinstance(related_data_result["data"], list):
            # Process the list of related keywords
            for item in related_data_result["data"]:
                 try:
                     related_keywords_processed.append({
                         "keyword": item.get("keyword"),
                         "search_volume": int(item.get("search_volume", 0)),
                         "relevance": float(item.get("relevance", 0.0))
                     })
                 except (ValueError, TypeError, KeyError) as e:
                     logger.warning(f"Could not process related keyword item {item}: {e}")
            logger.info(f"Successfully processed {len(related_keywords_processed)} related keywords.")
        else:
            related_error = "Unexpected format received for related keywords."
            logger.warning(f"{related_error} Response: {related_data_result}")


        # --- Combine results ---
        final_result = {}
        try:
            # Safely extract and convert overview data
            final_result["keyword"] = overview_data.get("keyword") # Already normalized header
            final_result["search_volume"] = int(overview_data.get("search_volume", 0))
            # SEMrush CPC might have currency symbols or commas, attempt clean conversion
            cpc_str = overview_data.get("cpc_(usd)", "0.0").replace('$', '').replace(',', '')
            final_result["cpc"] = float(cpc_str) if cpc_str else 0.0
            final_result["competition"] = float(overview_data.get("competition", 0.0))
            final_result["number_of_results"] = int(overview_data.get("number_of_results", 0))
            trend_str = overview_data.get("trend", "")
            final_result["trend"] = [int(t) for t in trend_str.split(',')] if trend_str else []

            # Add related keywords and any error message
            final_result["related_keywords"] = related_keywords_processed
            if related_error:
                final_result["related_keywords_error"] = related_error

            logger.info(f"SEMrushTool invocation finished successfully for keyword '{keyword}'.")

        except (ValueError, TypeError, KeyError) as e:
             logger.exception(f"Error processing combined SEMrush data for keyword '{keyword}': {e}")
             return {"error": f"Error processing SEMrush API response data: {e}", "raw_overview": overview_data, "raw_related": related_data_result}

        return final_result
