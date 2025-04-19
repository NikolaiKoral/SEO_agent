import os
import logging # Added import
from datetime import datetime, timedelta
from typing import Dict, Any, TypedDict, Optional, List

# A2A BaseTool import (assuming it's available in the environment)
try:
    from a2a.tools import BaseTool
except ImportError:
    class BaseTool:
        def __init__(self, config=None): pass
        async def invoke(self, args: Dict[str, Any]) -> Dict[str, Any]:
            return {"error": "a2a package not found"}

from google.oauth2 import service_account
from googleapiclient.discovery import build
# Import Google API errors if available
try:
    from googleapiclient.errors import HttpError as GoogleHttpError
except ImportError:
    GoogleHttpError = None # Define as None if google-api-client is not installed

# Setup logging
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class SearchConsoleInput(TypedDict):
    product_url: Optional[str]
    product_id: Optional[str]
    days: Optional[int]

class SearchConsoleTool(BaseTool):
    """Tool for retrieving data from Google Search Console"""

    def __init__(self, config=None):
        self.config = config or {}
        self.credentials_path = self.config.get("SEARCH_CONSOLE_CREDENTIALS") or os.environ.get("SEARCH_CONSOLE_CREDENTIALS")
        self.property_url = self.config.get("SEARCH_CONSOLE_PROPERTY") or os.environ.get("SEARCH_CONSOLE_PROPERTY")
        self.client = self._initialize_client()
        if self.client:
            logger.info("Search Console client initialized successfully.")
        else:
            logger.error("Search Console client failed to initialize.")

    def _initialize_client(self):
        """Initialize Search Console API client"""
        if not self.credentials_path or not os.path.exists(self.credentials_path):
            logger.error(f"Search Console credentials path not found or invalid: {self.credentials_path}")
            return None
        if not self.property_url:
            logger.error("Search Console property URL (SEARCH_CONSOLE_PROPERTY) not configured.")
            return None

        try:
            logger.debug(f"Initializing Search Console client with credentials: {self.credentials_path} for property: {self.property_url}")
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/webmasters.readonly'] # Use readonly scope
            )
            return build('searchconsole', 'v1', credentials=credentials)
        except Exception as e:
            logger.exception(f"Error initializing Search Console client: {e}")
            return None

    async def invoke(self, args: SearchConsoleInput) -> Dict[str, Any]:
        """Invoke the Search Console tool"""
        logger.info(f"Invoking SearchConsoleTool with args: {args}")
        if not self.client:
            logger.error("Search Console client not initialized, cannot invoke tool.")
            return {"error": "Search Console client not initialized"}

        product_url = args.get("product_url")
        product_id = args.get("product_id")
        days = args.get("days", 90)

        if not product_url and not product_id:
            logger.error("Missing required argument: either product_url or product_id must be provided.")
            return {"error": "Either product_url or product_id must be provided"}

        # Calculate date range
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        logger.debug(f"Calculated date range: {start_date} to {end_date}")

        # Determine page filter
        page_filter = None
        if product_url:
            page_filter = {"dimension": "page", "operator": "equals", "expression": product_url}
            logger.debug(f"Using page filter based on product_url: {product_url}")
        elif product_id:
            # Assuming a common URL structure like /products/{product_id}
            # This might need adjustment based on the actual URL structure
            page_path = f"/products/{product_id}" # TODO: Make this configurable?
            page_filter = {"dimension": "page", "operator": "contains", "expression": page_path}
            logger.debug(f"Using page filter based on product_id: {product_id} (path: {page_path})")

        if not page_filter:
             logger.error("Could not determine page filter from provided arguments.")
             return {"error": "Could not determine page filter"}

        try:
            # Request search analytics data
            request_body = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': ['query', 'device', 'page'], # Include page to verify filter worked if needed
                'rowLimit': 500, # Increased limit, consider making configurable
                'dimensionFilterGroups': [{
                    'filters': [page_filter]
                }]
            }
            logger.debug(f"Executing Search Console query for siteUrl: {self.property_url}, body: {request_body}")

            response = self.client.searchanalytics().query(
                siteUrl=self.property_url,
                body=request_body
            ).execute()

            logger.info(f"Successfully retrieved Search Console data for filter: {page_filter['expression']}")

            # Process the response
            search_data = self._process_search_analytics(response)

            # Get keyword opportunities based on the search data
            opportunities = self._get_keyword_opportunities(search_data)

            final_result = {
                "search_data": search_data,
                "keyword_opportunities": opportunities
            }
            logger.info(f"SearchConsoleTool invocation finished successfully.")
            return final_result

        except Exception as e:
            error_message = f"Error getting Search Console data: {e}"
            # Log more specific errors if google_exceptions is available
            if GoogleHttpError and isinstance(e, GoogleHttpError):
                 # Attempt to parse error details from Google API error
                 try:
                     error_details = json.loads(e.content).get('error', {}).get('message', str(e))
                     error_message = f"Google API Error getting Search Console data: {error_details}"
                 except:
                     error_message = f"Google API Error getting Search Console data: {e}" # Fallback
            logger.exception(error_message)
            return {"error": error_message, "details": str(e)}

    def _process_search_analytics(self, response):
        """Process Search Console response data"""
        logger.debug("Processing Search Console analytics response.")
        if 'rows' not in response or not response['rows']:
            logger.warning("No rows found in Search Console response.")
            return {
                "query_count": 0,
                "total_impressions": 0,
                "total_clicks": 0,
                "avg_ctr": 0.0,
                "avg_position": 0.0,
                "dominant_device": None,
                "device_breakdown": {},
                "queries": []
            }

        queries = {}
        devices = {"MOBILE": 0, "DESKTOP": 0, "TABLET": 0}
        total_impressions = 0.0
        total_clicks = 0.0
        weighted_position_sum = 0.0
        total_rows_processed = 0

        for row in response.get('rows', []):
            total_rows_processed += 1
            try:
                query = row['keys'][0]
                device = row['keys'][1]
                # page = row['keys'][2] # Page is filtered, less relevant for aggregation here

                impressions = float(row.get('impressions', 0))
                clicks = float(row.get('clicks', 0))
                ctr = float(row.get('ctr', 0)) * 100.0 # Convert to percentage
                position = float(row.get('position', 0))

                if query not in queries:
                    queries[query] = {"impressions": 0.0, "clicks": 0.0, "position_sum": 0.0, "devices": {"MOBILE": 0.0, "DESKTOP": 0.0, "TABLET": 0.0}}

                queries[query]["impressions"] += impressions
                queries[query]["clicks"] += clicks
                queries[query]["position_sum"] += position * impressions # Weighted position
                if device in queries[query]["devices"]: # Check if device key exists
                    queries[query]["devices"][device] += impressions

                total_impressions += impressions
                total_clicks += clicks
                weighted_position_sum += position * impressions
                if device in devices: devices[device] += impressions
            except (IndexError, KeyError, TypeError, ValueError) as e:
                logger.warning(f"Skipping row due to processing error: {e}. Row data: {row}")
                continue # Skip malformed rows

        logger.debug(f"Processed {total_rows_processed} rows from Search Console response.")

        sorted_queries = []
        for query, data in queries.items():
            avg_pos = data["position_sum"] / data["impressions"] if data["impressions"] > 0 else 0.0
            ctr = (data["clicks"] / data["impressions"]) * 100.0 if data["impressions"] > 0 else 0.0
            # Find dominant device based on impressions for that query
            dominant_device = max(data["devices"].items(), key=lambda item: item[1])[0] if any(d > 0 for d in data["devices"].values()) else None

            sorted_queries.append({
                "query": query,
                "impressions": int(data["impressions"]),
                "clicks": int(data["clicks"]),
                "ctr": round(ctr, 2),
                "avg_position": round(avg_pos, 1),
                "dominant_device": dominant_device
            })

        # Sort aggregated queries by impressions
        sorted_queries.sort(key=lambda x: x["impressions"], reverse=True)

        # Calculate overall averages
        avg_ctr = (total_clicks / total_impressions) * 100.0 if total_impressions > 0 else 0.0
        avg_position = weighted_position_sum / total_impressions if total_impressions > 0 else 0.0
        # Find overall dominant device
        dominant_device_overall = max(devices.items(), key=lambda item: item[1])[0] if any(d > 0 for d in devices.values()) else None
        # Calculate device breakdown percentage
        device_breakdown = {k: round((v / total_impressions) * 100.0, 1) if total_impressions > 0 else 0.0 for k, v in devices.items()}

        processed_data = {
            "query_count": len(queries),
            "total_impressions": int(total_impressions),
            "total_clicks": int(total_clicks),
            "avg_ctr": round(avg_ctr, 2),
            "avg_position": round(avg_position, 1),
            "dominant_device": dominant_device_overall,
            "device_breakdown": device_breakdown,
            "queries": sorted_queries[:50] # Return Top 50 queries
        }
        logger.debug(f"Finished processing search analytics. Queries found: {len(queries)}")
        return processed_data

    def _get_keyword_opportunities(self, search_data):
        """Identify keyword opportunities from processed search data"""
        logger.debug("Identifying keyword opportunities from search data.")
        high_impression_low_ctr = []
        already_ranking = []

        if not search_data or not search_data.get("queries"):
            logger.warning("No query data available for identifying keyword opportunities.")
            return {"high_impression_low_ctr": [], "already_ranking": []}

        for query_data in search_data.get("queries", []):
            try:
                impressions = query_data.get("impressions", 0)
                ctr = query_data.get("ctr", 0.0)
                position = query_data.get("avg_position", 1000.0) # Default high if missing
                query_text = query_data.get("query")

                if not query_text: continue # Skip if query text is missing

                # High impression but low CTR (e.g., > 100 impressions, < 2% CTR, position > 5)
                # Added position check to avoid flagging top results with naturally lower CTR
                if impressions > 100 and ctr < 2.0 and position > 5.0:
                    potential_clicks = int(impressions * 0.05) # Potential if CTR improved to 5%
                    high_impression_low_ctr.append({
                        "query": query_text,
                        "impressions": impressions,
                        "current_ctr": ctr,
                        "current_position": position,
                        "potential_clicks_gain": max(0, potential_clicks - query_data.get("clicks", 0)) # Gain over current
                    })

                # Already ranking well (e.g., position <= 10)
                if position <= 10.0:
                     already_ranking.append({
                        "query": query_text,
                        "position": position,
                        "clicks": query_data.get("clicks", 0),
                        "impressions": impressions,
                        "ctr": ctr
                     })
            except (TypeError, KeyError) as e:
                logger.warning(f"Skipping query opportunity due to data error: {e}. Query data: {query_data}")
                continue

        # Sort opportunities
        high_impression_low_ctr.sort(key=lambda x: x["impressions"], reverse=True)
        already_ranking.sort(key=lambda x: x["position"])

        opportunities = {
            "high_impression_low_ctr": high_impression_low_ctr[:10], # Top 10 opportunities
            "already_ranking": already_ranking[:10] # Top 10 ranking keywords
            # Could add 'rising_queries' if historical data comparison is implemented
        }
        logger.debug(f"Identified keyword opportunities: {len(high_impression_low_ctr)} low CTR, {len(already_ranking)} already ranking.")
        return opportunities
