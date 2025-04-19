import os
import json
import logging # Added import
from datetime import datetime, timedelta
from typing import Dict, Any, TypedDict, Optional, List
import re
import calendar

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

from google.oauth2.service_account import Credentials
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    DateRange,
    Dimension,
    Metric,
)
# Import Google API errors if available for more specific exception handling
try:
    from google.api_core import exceptions as google_exceptions
except ImportError:
    google_exceptions = None # Define as None if google-api-core is not installed

# Setup logging
logger = logging.getLogger(__name__)
# Configure logging basicConfig if not already configured elsewhere in the app
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class GAConnectorInput(TypedDict):
    product_id: Optional[str]
    brand: Optional[str]
    category: Optional[str]
    days: Optional[int]

class GAConnectorTool(BaseTool):
    """Tool for retrieving data from Google Analytics"""

    def __init__(self, config=None):
        # Configuration now primarily relies on environment variables
        # self.config = config or {} # config parameter is no longer used for these core settings
        self.property_id = os.environ.get("GA_PROPERTY_ID")
        self.credentials_path = os.environ.get("GA_CREDENTIALS_PATH")
        self.credentials_json = os.environ.get("GA_CREDENTIALS_JSON")
        self.ga_client = self._initialize_client()
        if self.ga_client:
            logger.info("Google Analytics client initialized successfully.")
        else:
            logger.error("Google Analytics client failed to initialize.")

    def _initialize_client(self):
        """Initialize GA client"""
        try:
            if self.credentials_json:
                logger.debug("Initializing GA client using credentials JSON.")
                service_account_info = json.loads(self.credentials_json)
                credentials = Credentials.from_service_account_info(
                    service_account_info,
                    scopes=["https://www.googleapis.com/auth/analytics.readonly"],
                )
                return BetaAnalyticsDataClient(credentials=credentials)
            elif self.credentials_path and os.path.exists(self.credentials_path):
                logger.debug(f"Initializing GA client using credentials file: {self.credentials_path}")
                credentials = Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=["https://www.googleapis.com/auth/analytics.readonly"],
                )
                return BetaAnalyticsDataClient(credentials=credentials)
            else:
                logger.error("No valid Google Analytics credentials found (checked path and JSON).")
                return None
        except Exception as e:
            logger.exception(f"Error initializing Google Analytics client: {e}") # Use logger.exception to include traceback
            return None

    async def invoke(self, args: GAConnectorInput) -> Dict[str, Any]:
        """Invoke the GA connector tool with provided arguments."""
        logger.info(f"Invoking GAConnectorTool with args: {args}")
        if not self.ga_client:
            logger.error("GA client not initialized, cannot invoke tool.")
            return {"error": "Google Analytics client not initialized"}
        if not self.property_id:
            logger.error("GA_PROPERTY_ID not configured, cannot invoke tool.")
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

        logger.info(f"GAConnectorTool invocation finished. Returning result keys: {list(result.keys())}")
        return result

    def _get_product_performance(self, product_id, days):
        """Get product performance metrics from GA."""
        logger.info(f"Fetching product performance for product_id: {product_id}, days: {days}")
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

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
                {"name": "conversions"}, # Ensure 'conversions' is the correct event name in GA4
                {"name": "cartToViewRate"},
                {"name": "averageSessionDuration"}
            ],
            date_ranges=[{"start_date": start_date, "end_date": end_date}],
            dimension_filter={
                "filter": {
                    "field_name": "pagePath", # Consider if 'landingPage' or 'pagePath' is more appropriate
                    "string_filter": {"match_type": "CONTAINS", "value": f"/products/{product_id}"} # Ensure this path matches your site structure
                }
            }
        )

        try:
            logger.debug(f"Running GA report request for product performance: {request}")
            response = self.ga_client.run_report(request)
            logger.info(f"Successfully retrieved product performance report for product_id: {product_id}")

            # Combine extraction results
            performance_data = {
                "traffic_patterns": self._extract_traffic_patterns(response),
                "search_pattern": self._extract_search_patterns(response), # Acknowledges limitation
                "conversion_metrics": self._extract_conversion_metrics(response),
                "seasonal_trends": self._identify_seasonal_trends(response),
                "user_segments": self._identify_user_segments(response)
            }
            return performance_data
        except Exception as e:
            error_message = f"Error getting product performance for product_id {product_id}: {e}"
            # Log more specific errors if google_exceptions is available
            if google_exceptions and isinstance(e, google_exceptions.GoogleAPIError):
                 error_message = f"Google API Error getting product performance for product_id {product_id}: {e}"
            logger.exception(error_message) # Use logger.exception
            return {"error": error_message, "details": str(e)} # Include original error string

    def _get_brand_keywords(self, brand, days):
        """Get brand keywords from GA search terms."""
        logger.info(f"Fetching brand keywords for brand: {brand}, days: {days}")
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        request = RunReportRequest(
            property=f"properties/{self.property_id}",
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimensions=[Dimension(name="searchTerm")],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="sessions"), # Ensure 'sessions' is available/correct for GA4
                Metric(name="conversions"), # Ensure 'conversions' is the correct event name
            ],
            dimension_filter={
                "filter": {
                    "field_name": "searchTerm",
                    "string_filter": {"match_type": "CONTAINS", "value": brand, "case_sensitive": False}
                }
            },
            limit=50, # Consider making limit configurable
        )

        try:
            logger.debug(f"Running GA report request for brand keywords: {request}")
            response = self.ga_client.run_report(request)
            logger.info(f"Successfully retrieved brand keywords report for brand: {brand}")

            keywords = []
            if response.rows:
                for row in response.rows:
                    term = self._get_dimension_value(row, 0)
                    views = self._get_metric_value(row, 0) # screenPageViews
                    sessions = self._get_metric_value(row, 1) # sessions
                    conversions = self._get_metric_value(row, 2) # conversions
                    # Avoid division by zero
                    conv_rate = (conversions / sessions * 100.0) if sessions > 0 else 0.0
                    keywords.append({
                        "term": term,
                        "views": int(views),
                        "sessions": int(sessions),
                        "conversions": int(conversions),
                        "conversion_rate": round(conv_rate, 2) # Round for cleaner output
                    })
            else:
                 logger.info(f"No brand keyword rows found for brand: {brand}")

            return {"keywords": keywords}
        except Exception as e:
            error_message = f"Error getting brand keywords for brand {brand}: {e}"
            if google_exceptions and isinstance(e, google_exceptions.GoogleAPIError):
                 error_message = f"Google API Error getting brand keywords for brand {brand}: {e}"
            logger.exception(error_message)
            return {"error": error_message, "details": str(e)}

    def _get_category_trends(self, category, days):
        """Get category trends (Placeholder)."""
        logger.warning(f"Category trends retrieval for category '{category}' is not yet implemented.")
        # Similar implementation to get_product_performance, but filtering by category
        # This might require different dimensions/metrics depending on how categories are tracked
        return {"error": "Category trends not yet implemented"}

    # Helper methods from the previous plan (EnhancedGAConnector)
    # Added basic logging within helpers
    def _extract_traffic_patterns(self, report):
        """Extract traffic patterns from GA report"""
        logger.debug("Extracting traffic patterns from report.")
        traffic_by_date = {}
        traffic_by_device = {}
        traffic_by_source = {}

        if not report or not report.rows:
            logger.warning("No rows found in report for traffic pattern extraction.")
            return { "top_sources": [], "device_preference": None, "growth_rate": 0.0, "traffic_trend": "unknown" }

        for row in report.rows:
            date = self._get_dimension_value(row, 0)
            device = self._get_dimension_value(row, 1)
            source = self._get_dimension_value(row, 2)

            page_views = self._get_metric_value(row, 0) # screenPageViews
            users = self._get_metric_value(row, 1) # totalUsers

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

        top_sources = sorted([{"source": k, "views": int(v["views"]), "users": int(v["users"])} for k, v in traffic_by_source.items()], key=lambda x: x["views"], reverse=True)[:5]
        device_preference = max(traffic_by_device.items(), key=lambda x: x[1]["views"])[0] if traffic_by_device else None

        growth_rate = 0.0
        dates = sorted(traffic_by_date.keys())
        if len(dates) > 1:
            mid_point = len(dates) // 2
            first_half_views = sum(traffic_by_date[d]["views"] for d in dates[:mid_point])
            second_half_views = sum(traffic_by_date[d]["views"] for d in dates[mid_point:])
            if first_half_views > 0: # Avoid division by zero
                growth_rate = ((second_half_views - first_half_views) / first_half_views) * 100.0

        traffic_trend = "increasing" if growth_rate > 10 else "decreasing" if growth_rate < -10 else "stable"
        logger.debug(f"Extracted traffic patterns: top_sources={len(top_sources)}, device={device_preference}, growth={growth_rate:.2f}%, trend={traffic_trend}")
        return {
            "top_sources": top_sources,
            "device_preference": device_preference,
            "growth_rate": round(growth_rate, 2),
            "traffic_trend": traffic_trend
        }

    def _extract_search_patterns(self, report):
        """Extract search patterns from GA report (Requires searchTerm dimension)"""
        # This method needs a report with 'searchTerm' dimension
        # The current _get_product_performance doesn't include it.
        logger.warning("Search term data not available in the provided report for search pattern extraction.")
        # Consider adding a separate GA call here if search terms are crucial and not included elsewhere
        return {"error": "Search term data not available in this report"}

    def _extract_conversion_metrics(self, report):
        """Extract conversion patterns from GA report"""
        logger.debug("Extracting conversion metrics from report.")
        total_views = 0.0
        total_conversions = 0.0
        cart_additions = 0.0 # Use float for calculated value

        if not report or not report.rows:
            logger.warning("No rows found in report for conversion metric extraction.")
            return { "conversion_rate": 0.0, "cart_abandonment_rate": 0.0, "revenue_per_view": 0.0 }

        for row in report.rows:
            views = self._get_metric_value(row, 0) # screenPageViews
            conversions = self._get_metric_value(row, 2) # conversions
            cart_to_view = self._get_metric_value(row, 3) # cartToViewRate

            total_views += views
            total_conversions += conversions
            # Ensure cart_to_view is treated as a percentage
            cart_additions += views * (cart_to_view / 100.0) if cart_to_view else 0.0

        conversion_rate = (total_conversions / total_views * 100.0) if total_views > 0 else 0.0
        # Calculate abandonment rate correctly
        cart_abandonment = (1.0 - (total_conversions / cart_additions)) * 100.0 if cart_additions > 0 else 0.0

        # Simplified revenue calculation - needs actual revenue metric from GA
        revenue_per_view = total_conversions / total_views if total_views > 0 else 0.0
        logger.warning("Revenue per view calculation is simplified and assumes 1 conversion = 1 unit of revenue. Add 'transactionRevenue' metric for accuracy.")

        logger.debug(f"Extracted conversion metrics: rate={conversion_rate:.2f}%, abandonment={cart_abandonment:.2f}%, rev_per_view={revenue_per_view:.2f}")
        return {
            "conversion_rate": round(conversion_rate, 2),
            "cart_abandonment_rate": round(cart_abandonment, 2),
            "revenue_per_view": round(revenue_per_view, 2) # Simplified
        }

    def _identify_seasonal_trends(self, report):
        """Identify seasonal trends from GA report"""
        logger.debug("Identifying seasonal trends from report.")
        traffic_by_date = {}

        if not report or not report.rows:
            logger.warning("No rows found in report for seasonal trend identification.")
            return {"is_seasonal": False, "peak_month": None, "lowest_month": None, "peak_value": 0.0, "lowest_value": 0.0}

        for row in report.rows:
            date_str = self._get_dimension_value(row, 0) # Assumes date is first dimension
            views = self._get_metric_value(row, 0) # Assumes views is first metric
            if date_str:
                # GA4 date format is YYYYMMDD
                traffic_by_date[date_str] = traffic_by_date.get(date_str, 0) + views

        if not traffic_by_date:
            logger.debug("No valid date data found for seasonal trend analysis.")
            return {"is_seasonal": False, "peak_month": None, "lowest_month": None, "peak_value": 0.0, "lowest_value": 0.0}

        monthly_averages = {}
        for date_str, views in traffic_by_date.items():
            try:
                # Ensure parsing matches GA4 format
                date = datetime.strptime(date_str, "%Y%m%d")
                month = date.strftime("%B") # Use month name as key
                if month not in monthly_averages: monthly_averages[month] = {"sum": 0.0, "count": 0}
                monthly_averages[month]["sum"] += views
                monthly_averages[month]["count"] += 1
            except ValueError:
                logger.warning(f"Could not parse date string: {date_str}")
                continue # Skip malformed dates

        if not monthly_averages:
            logger.debug("No monthly averages calculated for seasonal trend analysis.")
            return {"is_seasonal": False, "peak_month": None, "lowest_month": None, "peak_value": 0.0, "lowest_value": 0.0}

        for month, data in monthly_averages.items():
            data["average"] = data["sum"] / data["count"] if data["count"] > 0 else 0.0

        peak_month_data = max(monthly_averages.items(), key=lambda x: x[1]["average"])
        lowest_month_data = min(monthly_averages.items(), key=lambda x: x[1]["average"])

        # Check if lowest month average is greater than zero before division
        is_seasonal = False
        if lowest_month_data[1]["average"] > 0:
            is_seasonal = peak_month_data[1]["average"] > lowest_month_data[1]["average"] * 1.5 # 50% higher peak indicates seasonality

        logger.debug(f"Seasonal analysis: is_seasonal={is_seasonal}, peak={peak_month_data[0]}, low={lowest_month_data[0]}")
        return {
            "is_seasonal": is_seasonal,
            "peak_month": peak_month_data[0],
            "peak_value": round(peak_month_data[1]["average"], 2),
            "lowest_month": lowest_month_data[0],
            "lowest_value": round(lowest_month_data[1]["average"], 2),
        }

    def _identify_user_segments(self, report):
        """Identify valuable user segments based on device and source."""
        logger.debug("Identifying user segments from report.")
        segments = {}

        if not report or not report.rows:
            logger.warning("No rows found in report for user segment identification.")
            return {"high_value_segments": []}

        for row in report.rows:
            device = self._get_dimension_value(row, 1) # deviceCategory
            source = self._get_dimension_value(row, 2) # sessionSource
            if not device or not source: continue

            users = self._get_metric_value(row, 1) # totalUsers
            conversions = self._get_metric_value(row, 2) # conversions
            duration = self._get_metric_value(row, 4) # averageSessionDuration

            segment_key = f"{device}|{source}"
            if segment_key not in segments:
                segments[segment_key] = {"device": device, "source": source, "users": 0.0, "conversions": 0.0, "total_duration": 0.0}

            segments[segment_key]["users"] += users
            segments[segment_key]["conversions"] += conversions
            segments[segment_key]["total_duration"] += duration * users # Weighted duration

        for segment in segments.values():
            segment["avg_duration"] = segment["total_duration"] / segment["users"] if segment["users"] > 0 else 0.0
            segment["conversion_rate"] = (segment["conversions"] / segment["users"] * 100.0) if segment["users"] > 0 else 0.0
            # Round values for cleaner output
            segment["avg_duration"] = round(segment["avg_duration"], 2)
            segment["conversion_rate"] = round(segment["conversion_rate"], 2)
            # Convert counts back to int for clarity if desired
            segment["users"] = int(segment["users"])
            segment["conversions"] = int(segment["conversions"])


        # Sort by conversion rate first, then users as a tie-breaker
        high_value_segments = sorted(
            list(segments.values()),
            key=lambda x: (x["conversion_rate"], x["users"]),
            reverse=True
        )[:3] # Get top 3

        logger.debug(f"Identified {len(high_value_segments)} high-value user segments.")
        return {"high_value_segments": high_value_segments}

    def _get_dimension_value(self, row, index):
        """Helper to safely get dimension value from a GA report row."""
        try:
            return row.dimension_values[index].value
        except (IndexError, AttributeError):
            # logger.debug(f"Could not get dimension value at index {index} from row.") # Optional: more verbose logging
            return None

    def _get_metric_value(self, row, index):
        """Helper to safely get metric value from a GA report row."""
        try:
            # GA4 metric values are strings, attempt to convert
            value_str = row.metric_values[index].value
            # Handle potential float conversion
            try:
                # Return as float for calculations, convert to int later if needed
                return float(value_str)
            except ValueError:
                logger.warning(f"Could not convert metric value '{value_str}' to float at index {index}.")
                return 0.0 # Return 0.0 float if conversion fails
        except (IndexError, AttributeError):
            # logger.debug(f"Could not get metric value at index {index} from row.") # Optional: more verbose logging
            return 0.0 # Default to 0.0 float if metric is missing
