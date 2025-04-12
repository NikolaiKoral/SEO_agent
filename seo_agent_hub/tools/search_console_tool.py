import os
from datetime import datetime, timedelta
from typing import Dict, Any, TypedDict, Optional, List

from a2a.tools import BaseTool
from google.oauth2 import service_account
from googleapiclient.discovery import build

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
    
    def _initialize_client(self):
        """Initialize Search Console API client"""
        if not self.credentials_path or not os.path.exists(self.credentials_path):
            print("Search Console credentials path not found or not configured.")
            return None
        if not self.property_url:
            print("Search Console property URL not configured.")
            return None
            
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/webmasters.readonly'] # Use readonly scope
            )
            return build('searchconsole', 'v1', credentials=credentials)
        except Exception as e:
            print(f"Error initializing Search Console client: {e}")
            return None

    async def invoke(self, args: SearchConsoleInput) -> Dict[str, Any]:
        """Invoke the Search Console tool"""
        if not self.client:
            return {"error": "Search Console client not initialized"}
            
        product_url = args.get("product_url")
        product_id = args.get("product_id")
        days = args.get("days", 90)
        
        if not product_url and not product_id:
            return {"error": "Either product_url or product_id must be provided"}
            
        # Calculate date range
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # Determine page filter
        page_filter = None
        if product_url:
            page_filter = {"dimension": "page", "operator": "equals", "expression": product_url}
        elif product_id:
            # Assuming a common URL structure like /products/{product_id}
            # This might need adjustment based on the actual URL structure
            page_path = f"/products/{product_id}" 
            page_filter = {"dimension": "page", "operator": "contains", "expression": page_path}
        
        if not page_filter:
             return {"error": "Could not determine page filter"}

        try:
            # Request search analytics data
            request_body = {
                'startDate': start_date,
                'endDate': end_date,
                'dimensions': ['query', 'device', 'page'],
                'rowLimit': 500, # Increased limit
                'dimensionFilterGroups': [{
                    'filters': [page_filter]
                }]
            }
            
            response = self.client.searchanalytics().query(
                siteUrl=self.property_url,
                body=request_body
            ).execute()
            
            # Process the response
            search_data = self._process_search_analytics(response)
            
            # Get keyword opportunities based on the search data
            opportunities = self._get_keyword_opportunities(search_data)

            return {
                "search_data": search_data,
                "keyword_opportunities": opportunities
            }

        except Exception as e:
            return {"error": f"Error getting Search Console data: {e}"}

    def _process_search_analytics(self, response):
        """Process Search Console response data"""
        if 'rows' not in response:
            return {
                "query_count": 0,
                "total_impressions": 0,
                "total_clicks": 0,
                "avg_ctr": 0,
                "avg_position": 0, # Position data might not always be present or accurate
                "queries": []
            }
        
        queries = {}
        devices = {"MOBILE": 0, "DESKTOP": 0, "TABLET": 0}
        total_impressions = 0
        total_clicks = 0
        weighted_position_sum = 0
        
        for row in response.get('rows', []):
            query = row['keys'][0]
            device = row['keys'][1]
            # page = row['keys'][2] # Page is filtered, so less relevant here
            
            impressions = row.get('impressions', 0)
            clicks = row.get('clicks', 0)
            ctr = row.get('ctr', 0) * 100 # Convert to percentage
            position = row.get('position', 0)
            
            if query not in queries:
                queries[query] = {"impressions": 0, "clicks": 0, "position_sum": 0, "devices": {"MOBILE": 0, "DESKTOP": 0, "TABLET": 0}}
            
            queries[query]["impressions"] += impressions
            queries[query]["clicks"] += clicks
            queries[query]["position_sum"] += position * impressions # Weighted position
            queries[query]["devices"][device] += impressions
            
            total_impressions += impressions
            total_clicks += clicks
            weighted_position_sum += position * impressions
            if device in devices: devices[device] += impressions
        
        sorted_queries = []
        for query, data in queries.items():
            avg_pos = data["position_sum"] / data["impressions"] if data["impressions"] > 0 else 0
            ctr = (data["clicks"] / data["impressions"]) * 100 if data["impressions"] > 0 else 0
            dominant_device = max(data["devices"].items(), key=lambda x: x[1])[0] if any(data["devices"].values()) else None
            
            sorted_queries.append({
                "query": query,
                "impressions": data["impressions"],
                "clicks": data["clicks"],
                "ctr": round(ctr, 2),
                "avg_position": round(avg_pos, 1),
                "dominant_device": dominant_device
            })
        
        sorted_queries.sort(key=lambda x: x["impressions"], reverse=True)
        
        avg_ctr = (total_clicks / total_impressions) * 100 if total_impressions > 0 else 0
        avg_position = weighted_position_sum / total_impressions if total_impressions > 0 else 0
        dominant_device = max(devices.items(), key=lambda x: x[1])[0] if any(devices.values()) else None
        
        return {
            "query_count": len(queries),
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "avg_ctr": round(avg_ctr, 2),
            "avg_position": round(avg_position, 1),
            "dominant_device": dominant_device,
            "device_breakdown": {k: round((v / total_impressions) * 100, 1) if total_impressions > 0 else 0 for k, v in devices.items()},
            "queries": sorted_queries[:50] # Top 50 queries
        }

    def _get_keyword_opportunities(self, search_data):
        """Identify keyword opportunities from search data"""
        high_impression_low_ctr = []
        already_ranking = []
        
        for query in search_data.get("queries", []):
            # High impression but low CTR (e.g., > 100 impressions, < 2% CTR)
            if query["impressions"] > 100 and query["ctr"] < 2.0:
                high_impression_low_ctr.append({
                    "query": query["query"],
                    "impressions": query["impressions"],
                    "current_ctr": query["ctr"],
                    "potential_clicks": int(query["impressions"] * 0.05) # Potential if CTR improved to 5%
                })
            
            # Already ranking well (e.g., position <= 10)
            if query.get("avg_position", 100) <= 10:
                 already_ranking.append({
                    "query": query["query"],
                    "position": query["avg_position"],
                    "clicks": query["clicks"],
                    "impressions": query["impressions"]
                 })

        # Sort opportunities
        high_impression_low_ctr.sort(key=lambda x: x["impressions"], reverse=True)
        already_ranking.sort(key=lambda x: x["position"])

        return {
            "high_impression_low_ctr": high_impression_low_ctr[:10], # Top 10 opportunities
            "already_ranking": already_ranking[:10] # Top 10 ranking keywords
            # Could add 'rising_queries' if historical data comparison is implemented
        }
