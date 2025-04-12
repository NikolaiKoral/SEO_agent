import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, TypedDict, Optional, List
import re
import calendar

from a2a.tools import BaseTool
from google.oauth2.service_account import Credentials
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    DateRange,
    Dimension,
    Metric,
)

class GAConnectorInput(TypedDict):
    product_id: Optional[str]
    brand: Optional[str]
    category: Optional[str]
    days: Optional[int]

class GAConnectorTool(BaseTool):
    """Tool for retrieving data from Google Analytics"""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.property_id = self.config.get("GA_PROPERTY_ID") or os.environ.get("GA_PROPERTY_ID")
        self.credentials_path = self.config.get("GA_CREDENTIALS_PATH") or os.environ.get("GA_CREDENTIALS_PATH")
        self.credentials_json = self.config.get("GA_CREDENTIALS_JSON") or os.environ.get("GA_CREDENTIALS_JSON")
        self.ga_client = self._initialize_client()
    
    def _initialize_client(self):
        """Initialize GA client"""
        try:
            if self.credentials_json:
                service_account_info = json.loads(self.credentials_json)
                credentials = Credentials.from_service_account_info(
                    service_account_info,
                    scopes=["https://www.googleapis.com/auth/analytics.readonly"],
                )
                return BetaAnalyticsDataClient(credentials=credentials)
            elif self.credentials_path and os.path.exists(self.credentials_path):
                credentials = Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=["https://www.googleapis.com/auth/analytics.readonly"],
                )
                return BetaAnalyticsDataClient(credentials=credentials)
            else:
                print("No valid Google Analytics credentials found.")
                return None
        except Exception as e:
            print(f"Error initializing Google Analytics client: {e}")
            return None

    async def invoke(self, args: GAConnectorInput) -> Dict[str, Any]:
        """Invoke the GA connector tool"""
        if not self.ga_client:
            return {"error": "Google Analytics client not initialized"}
        if not self.property_id:
            return {"error": "GA_PROPERTY_ID not configured"}

        product_id = args.get("product_id")
        brand = args.get("brand")
        category = args.get("category")
        days = args.get("days", 90)
        
        result = {}
        
        # Get product performance metrics if product_id is provided
        if product_id:
            result["performance_metrics"] = self._get_product_performance(product_id, days)
        
        # Get brand keywords if brand is provided
        if brand:
            result["brand_keywords"] = self._get_brand_keywords(brand, days)

        # Get category trends if category is provided
        if category:
            result["category_trends"] = self._get_category_trends(category, days)
        
        return result
    
    def _get_product_performance(self, product_id, days):
        """Get product performance metrics"""
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        try:
            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                dimensions=[
                    {"name": "date"},
                    {"name": "deviceCategory"},
                    {"name": "sessionSource"}, 
                    {"name": "landingPage"}
                ],
                metrics=[
                    {"name": "screenPageViews"},
                    {"name": "totalUsers"}, 
                    {"name": "conversions"},
                    {"name": "cartToViewRate"},
                    {"name": "averageSessionDuration"}
                ],
                date_ranges=[{"start_date": start_date, "end_date": end_date}],
                dimension_filter={
                    "filter": {
                        "field_name": "pagePath",
                        "string_filter": {"match_type": "CONTAINS", "value": f"/products/{product_id}"}
                    }
                }
            )
            response = self.ga_client.run_report(request)
            return {
                "traffic_patterns": self._extract_traffic_patterns(response),
                "search_pattern": self._extract_search_patterns(response), # Need separate report for this
                "conversion_metrics": self._extract_conversion_metrics(response),
                "seasonal_trends": self._identify_seasonal_trends(response),
                "user_segments": self._identify_user_segments(response)
            }
        except Exception as e:
            return {"error": f"Error getting product performance: {e}"}

    def _get_brand_keywords(self, brand, days):
        """Get brand keywords"""
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        try:
            request = RunReportRequest(
                property=f"properties/{self.property_id}",
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name="searchTerm")],
                metrics=[
                    Metric(name="screenPageViews"),
                    Metric(name="sessions"),
                    Metric(name="conversions"),
                ],
                dimension_filter={
                    "filter": {
                        "field_name": "searchTerm",
                        "string_filter": {"match_type": "CONTAINS", "value": brand}
                    }
                },
                limit=50,
            )
            response = self.ga_client.run_report(request)
            
            keywords = []
            if response.rows:
                for row in response.rows:
                    term = self._get_dimension_value(row, 0)
                    views = int(self._get_metric_value(row, 0))
                    sessions = int(self._get_metric_value(row, 1))
                    conversions = int(self._get_metric_value(row, 2))
                    conv_rate = (conversions / sessions * 100) if sessions > 0 else 0
                    keywords.append({
                        "term": term,
                        "views": views,
                        "sessions": sessions,
                        "conversions": conversions,
                        "conversion_rate": conv_rate
                    })
            
            return {"keywords": keywords}
        except Exception as e:
            return {"error": f"Error getting brand keywords: {e}"}

    def _get_category_trends(self, category, days):
        """Get category trends"""
        # Similar implementation to get_product_performance, but filtering by category
        # This might require different dimensions/metrics depending on how categories are tracked
        return {"error": "Category trends not yet implemented"}

    # Helper methods from the previous plan (EnhancedGAConnector)
    def _extract_traffic_patterns(self, report):
        """Extract traffic patterns from GA report"""
        traffic_by_date = {}
        traffic_by_device = {}
        traffic_by_source = {}
        
        for row in report.rows:
            date = self._get_dimension_value(row, 0)
            device = self._get_dimension_value(row, 1)
            source = self._get_dimension_value(row, 2)
            
            page_views = int(self._get_metric_value(row, 0))
            users = int(self._get_metric_value(row, 1))
            
            if date:
                if date not in traffic_by_date: traffic_by_date[date] = {"views": 0, "users": 0}
                traffic_by_date[date]["views"] += page_views
                traffic_by_date[date]["users"] += users
            if device:
                if device not in traffic_by_device: traffic_by_device[device] = {"views": 0, "users": 0}
                traffic_by_device[device]["views"] += page_views
                traffic_by_device[device]["users"] += users
            if source:
                if source not in traffic_by_source: traffic_by_source[source] = {"views": 0, "users": 0}
                traffic_by_source[source]["views"] += page_views
                traffic_by_source[source]["users"] += users
        
        top_sources = sorted([{"source": k, **v} for k, v in traffic_by_source.items()], key=lambda x: x["views"], reverse=True)[:5]
        device_preference = max(traffic_by_device.items(), key=lambda x: x[1]["views"])[0] if traffic_by_device else None
        
        growth_rate = 0
        dates = sorted(traffic_by_date.keys())
        if len(dates) > 1:
            mid_point = len(dates) // 2
            first_half_views = sum(traffic_by_date[d]["views"] for d in dates[:mid_point])
            second_half_views = sum(traffic_by_date[d]["views"] for d in dates[mid_point:])
            growth_rate = ((second_half_views - first_half_views) / first_half_views) * 100 if first_half_views > 0 else 0
        
        return {
            "top_sources": top_sources,
            "device_preference": device_preference,
            "growth_rate": growth_rate,
            "traffic_trend": "increasing" if growth_rate > 10 else "decreasing" if growth_rate < -10 else "stable"
        }

    def _extract_search_patterns(self, report):
        """Extract search patterns from GA report (Requires searchTerm dimension)"""
        # This method needs a report with 'searchTerm' dimension
        # The current _get_product_performance doesn't include it.
        # A separate report call might be needed or modify the existing one.
        return {"error": "Search term data not available in this report"}

    def _extract_conversion_metrics(self, report):
        """Extract conversion patterns from GA report"""
        total_views = 0
        total_conversions = 0
        cart_additions = 0
        
        for row in report.rows:
            views = int(self._get_metric_value(row, 0))
            conversions = int(self._get_metric_value(row, 2))
            cart_to_view = float(self._get_metric_value(row, 3)) # cartToViewRate
            
            total_views += views
            total_conversions += conversions
            cart_additions += views * (cart_to_view / 100) if cart_to_view else 0
        
        conversion_rate = (total_conversions / total_views) * 100 if total_views > 0 else 0
        cart_abandonment = 100 - ((total_conversions / cart_additions) * 100) if cart_additions > 0 else 0
        
        return {
            "conversion_rate": conversion_rate,
            "cart_abandonment_rate": cart_abandonment,
            "revenue_per_view": total_conversions / total_views if total_views > 0 else 0 # Simplified, needs revenue metric
        }

    def _identify_seasonal_trends(self, report):
        """Identify seasonal trends from GA report"""
        traffic_by_date = {}
        for row in report.rows:
            date_str = self._get_dimension_value(row, 0) # Assumes date is first dimension
            views = int(self._get_metric_value(row, 0)) # Assumes views is first metric
            if date_str:
                traffic_by_date[date_str] = traffic_by_date.get(date_str, 0) + views

        if not traffic_by_date: return {"is_seasonal": False}

        monthly_averages = {}
        for date_str, views in traffic_by_date.items():
            try:
                date = datetime.strptime(date_str, "%Y%m%d")
                month = date.strftime("%B")
                if month not in monthly_averages: monthly_averages[month] = {"sum": 0, "count": 0}
                monthly_averages[month]["sum"] += views
                monthly_averages[month]["count"] += 1
            except ValueError: continue

        for month, data in monthly_averages.items():
            data["average"] = data["sum"] / data["count"] if data["count"] > 0 else 0

        if not monthly_averages: return {"is_seasonal": False}

        peak_month = max(monthly_averages.items(), key=lambda x: x[1]["average"])
        lowest_month = min(monthly_averages.items(), key=lambda x: x[1]["average"])
        is_seasonal = peak_month[1]["average"] > lowest_month[1]["average"] * 1.5

        return {
            "is_seasonal": is_seasonal,
            "peak_month": peak_month[0],
            "peak_value": peak_month[1]["average"],
            "lowest_month": lowest_month[0],
            "lowest_value": lowest_month[1]["average"],
        }

    def _identify_user_segments(self, report):
        """Identify valuable user segments"""
        segments = {}
        for row in report.rows:
            device = self._get_dimension_value(row, 1) # deviceCategory
            source = self._get_dimension_value(row, 2) # sessionSource
            if not device or not source: continue

            users = int(self._get_metric_value(row, 1)) # totalUsers
            conversions = int(self._get_metric_value(row, 2)) # conversions
            duration = float(self._get_metric_value(row, 4)) # averageSessionDuration

            segment_key = f"{device}|{source}"
            if segment_key not in segments:
                segments[segment_key] = {"device": device, "source": source, "users": 0, "conversions": 0, "total_duration": 0}
            
            segments[segment_key]["users"] += users
            segments[segment_key]["conversions"] += conversions
            segments[segment_key]["total_duration"] += duration * users

        for segment in segments.values():
            segment["avg_duration"] = segment["total_duration"] / segment["users"] if segment["users"] > 0 else 0
            segment["conversion_rate"] = (segment["conversions"] / segment["users"]) * 100 if segment["users"] > 0 else 0

        high_value_segments = sorted(list(segments.values()), key=lambda x: x["conversion_rate"], reverse=True)[:3]
        
        return {"high_value_segments": high_value_segments}

    def _get_dimension_value(self, row, index):
        """Helper to safely get dimension value"""
        try: return row.dimension_values[index].value
        except (IndexError, AttributeError): return None
    
    def _get_metric_value(self, row, index):
        """Helper to safely get metric value"""
        try: return row.metric_values[index].value
        except (IndexError, AttributeError): return 0
