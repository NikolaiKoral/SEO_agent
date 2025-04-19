import os
import logging # Added import
from typing import Dict, Any, TypedDict, Optional, List
import pandas as pd # pytrends returns pandas DataFrames

# Need to handle potential import error if pytrends is not installed
try:
    from pytrends.request import TrendReq
    PYTRENDS_AVAILABLE = True
except ImportError:
    TrendReq = None
    PYTRENDS_AVAILABLE = False

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


class GoogleTrendsInput(TypedDict):
    keyword: str
    timeframe: Optional[str] # e.g., 'today 12-m', 'today 3-m', 'now 7-d'
    geo: Optional[str] # e.g., 'US', 'DK', '' for worldwide

class GoogleTrendsTool(BaseTool):
    """Tool for retrieving data from Google Trends using pytrends"""

    def __init__(self, config=None):
        self.config = config or {}
        if not PYTRENDS_AVAILABLE:
            logger.error("pytrends package not found. Google Trends tool will be disabled.")
            self.pytrends = None
        else:
            try:
                # Initialize pytrends client
                # Consider adding parameters for hl (language) and tz (timezone) if needed
                logger.debug("Initializing pytrends TrendReq client.")
                self.pytrends = TrendReq(hl='en-US', tz=360) # Example: US English, Central Timezone offset
                logger.info("Google Trends client (pytrends) initialized successfully.")
            except Exception as e:
                 logger.exception("Error initializing pytrends TrendReq client.")
                 self.pytrends = None

    async def invoke(self, args: GoogleTrendsInput) -> Dict[str, Any]:
        """Invoke the Google Trends tool"""
        logger.info(f"Invoking GoogleTrendsTool with args: {args}")
        if not self.pytrends:
            logger.error("pytrends client not initialized, cannot invoke tool.")
            return {"error": "pytrends package not installed or TrendReq failed to initialize"}

        keyword = args.get("keyword")
        timeframe = args.get("timeframe", 'today 12-m') # Default to last 12 months
        geo = args.get("geo", '') # Default to worldwide

        if not keyword:
            logger.error("Missing required argument: keyword")
            return {"error": "Keyword is required"}

        try:
            # Build the payload
            logger.debug(f"Building pytrends payload for keyword: '{keyword}', timeframe: '{timeframe}', geo: '{geo}'")
            # Using kw_list for clarity, even though it's just one keyword here
            self.pytrends.build_payload(kw_list=[keyword], cat=0, timeframe=timeframe, geo=geo, gprop='')
            logger.info(f"Successfully built payload for '{keyword}'.")

            # Get interest over time
            logger.debug("Fetching interest over time...")
            interest_over_time_df = self.pytrends.interest_over_time()
            logger.info(f"Interest over time data fetched. DataFrame shape: {interest_over_time_df.shape}")

            # Get related topics and queries
            related_topics_dict = {}
            related_queries_dict = {}
            logger.debug("Fetching related topics...")
            try:
                 related_topics_dict = self.pytrends.related_topics()
                 logger.info("Related topics data fetched.")
            except Exception as e:
                 logger.warning(f"Could not fetch related topics for '{keyword}': {e}", exc_info=True) # Log exception info

            logger.debug("Fetching related queries...")
            try:
                 related_queries_dict = self.pytrends.related_queries()
                 logger.info("Related queries data fetched.")
            except Exception as e:
                 logger.warning(f"Could not fetch related queries for '{keyword}': {e}", exc_info=True) # Log exception info


            # Format the response
            logger.debug("Formatting final trend data response.")
            trend_data = {
                "interest_over_time": self._format_interest_data(interest_over_time_df, keyword),
                "related_topics": self._extract_related_data(related_topics_dict.get(keyword, {}), "topics"),
                "related_queries": self._extract_related_data(related_queries_dict.get(keyword, {}), "queries"),
                "is_rising": self._determine_if_rising(interest_over_time_df, keyword),
                "seasonality": self._analyze_seasonality(interest_over_time_df, keyword),
            }

            logger.info(f"GoogleTrendsTool invocation finished successfully for keyword '{keyword}'.")
            return trend_data

        except Exception as e:
            # Catch potential exceptions from pytrends (e.g., rate limits, request errors, parsing errors)
            error_message = f"Error getting Google Trends data for '{keyword}': {e}"
            logger.exception(error_message) # Log full traceback
            # Check for specific pytrends error types if needed, e.g., ResponseError
            # from pytrends.exceptions import ResponseError
            # if isinstance(e, ResponseError): ...
            return {"error": error_message, "details": str(e)}

    def _format_interest_data(self, interest_df, keyword):
        """Format interest over time data"""
        logger.debug(f"Formatting interest over time data for keyword '{keyword}'.")
        if not isinstance(interest_df, pd.DataFrame) or interest_df.empty:
            logger.warning(f"Interest DataFrame is empty or not a DataFrame for keyword '{keyword}'.")
            return []
        if keyword not in interest_df.columns:
            logger.warning(f"Keyword '{keyword}' not found in interest DataFrame columns: {interest_df.columns}")
            return []

        interest_data = []
        # Ensure 'isPartial' column exists, default to False if not
        if 'isPartial' not in interest_df.columns:
             logger.debug("'isPartial' column not found, adding default False.")
             interest_df['isPartial'] = False # Add default value

        try:
            for index, row in interest_df.iterrows():
                # Convert index (Timestamp) to string
                date_str = index.strftime("%Y-%m-%d")
                value = int(row[keyword])
                is_partial = bool(row['isPartial'])

                interest_data.append({
                    "date": date_str,
                    "value": value,
                    "is_partial": is_partial
                })
            logger.debug(f"Formatted {len(interest_data)} interest data points.")
        except Exception as e:
            logger.exception(f"Error formatting interest data row: {e}")
            # Decide whether to return partial data or an error indicator
            return {"error": f"Error during interest data formatting: {e}"}

        return interest_data

    def _extract_related_data(self, related_data, data_type: str):
        """Extract related topics or queries"""
        logger.debug(f"Extracting related {data_type} data.")
        rising = []
        top = []

        # Check if related_data is a dictionary and has the expected keys
        if isinstance(related_data, dict):
            rising_df = related_data.get('rising')
            top_df = related_data.get('top')

            # Convert DataFrames to dictionaries if they exist and are not None/empty
            if isinstance(rising_df, pd.DataFrame) and not rising_df.empty:
                try:
                    rising = rising_df.to_dict('records')
                    logger.debug(f"Extracted {len(rising)} rising related {data_type}.")
                except Exception as e:
                    logger.warning(f"Could not convert rising related {data_type} DataFrame to dict: {e}")
            else:
                 logger.debug(f"No rising related {data_type} DataFrame found or it's empty.")

            if isinstance(top_df, pd.DataFrame) and not top_df.empty:
                try:
                    top = top_df.to_dict('records')
                    logger.debug(f"Extracted {len(top)} top related {data_type}.")
                except Exception as e:
                    logger.warning(f"Could not convert top related {data_type} DataFrame to dict: {e}")
            else:
                 logger.debug(f"No top related {data_type} DataFrame found or it's empty.")
        else:
            logger.warning(f"Input for related {data_type} was not a dictionary: {type(related_data)}")

        return {"rising": rising, "top": top}

    def _determine_if_rising(self, interest_df, keyword):
        """Determine if keyword interest is rising based on simple comparison."""
        logger.debug(f"Determining if trend is rising for keyword '{keyword}'.")
        if not isinstance(interest_df, pd.DataFrame) or interest_df.empty:
            logger.warning("Cannot determine rising trend: Interest DataFrame is empty.")
            return False
        if keyword not in interest_df.columns:
            logger.warning(f"Cannot determine rising trend: Keyword '{keyword}' not in DataFrame.")
            return False
        if len(interest_df) < 4: # Need at least a few points to compare
            logger.warning(f"Cannot determine rising trend: Insufficient data points ({len(interest_df)}).")
            return False

        try:
            values = interest_df[keyword].tolist()

            # Simple check: compare last value to average of first half
            # More robust methods could involve regression or time series analysis
            if len(values) >= 10: # Require at least 10 points for this simple check
                 last_value = values[-1]
                 first_half_len = len(values) // 2
                 avg_first_half = sum(values[:first_half_len]) / first_half_len if first_half_len > 0 else 0
                 # Consider rising if last value is > 20% above the first half average and average is not zero
                 is_rising = last_value > avg_first_half * 1.2 and avg_first_half > 0
                 logger.debug(f"Rising check: last={last_value}, avg_first_half={avg_first_half:.2f}, is_rising={is_rising}")
                 return is_rising
            else:
                 logger.debug(f"Not enough data points ({len(values)}) for simple rising trend check.")
                 return False # Not enough data for this specific simple trend check
        except Exception as e:
            logger.exception(f"Error during rising trend determination: {e}")
            return False # Default to False on error

    def _analyze_seasonality(self, interest_df, keyword):
        """Analyze seasonality patterns using monthly averages."""
        logger.debug(f"Analyzing seasonality for keyword '{keyword}'.")
        min_data_points = 12 # Need at least a year of data ideally
        default_result = {"is_seasonal": False, "reason": "Analysis could not be completed", "peak_month": None, "lowest_month": None, "peak_value": 0.0, "lowest_value": 0.0, "monthly_averages": {}}

        if not isinstance(interest_df, pd.DataFrame) or interest_df.empty:
            logger.warning("Cannot analyze seasonality: Interest DataFrame is empty.")
            default_result["reason"] = "Interest data is empty"
            return default_result
        if keyword not in interest_df.columns:
            logger.warning(f"Cannot analyze seasonality: Keyword '{keyword}' not in DataFrame.")
            default_result["reason"] = f"Keyword '{keyword}' not found in data"
            return default_result
        if len(interest_df) < min_data_points:
            logger.warning(f"Cannot analyze seasonality: Insufficient data points ({len(interest_df)}), need at least {min_data_points}.")
            default_result["reason"] = f"Insufficient data points ({len(interest_df)}), need {min_data_points}"
            return default_result

        try:
            # Ensure index is DatetimeIndex
            if not isinstance(interest_df.index, pd.DatetimeIndex):
                 logger.warning("Interest DataFrame index is not DatetimeIndex, attempting conversion.")
                 # This assumes the index can be converted, might fail
                 interest_df.index = pd.to_datetime(interest_df.index)

            # Group by month
            monthly_averages = interest_df.groupby(interest_df.index.month)[keyword].mean()

            if len(monthly_averages) < 12:
                 logger.warning(f"Seasonality analysis incomplete: Data covers only {len(monthly_averages)} months.")
                 default_result["reason"] = f"Data covers only {len(monthly_averages)} months"
                 # Still return partial averages if calculated
                 month_names_partial = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                 default_result["monthly_averages"] = {month_names_partial[m]: round(v, 2) for m, v in monthly_averages.items()}
                 return default_result

            # Find peak and lowest months
            peak_month_num = monthly_averages.idxmax()
            lowest_month_num = monthly_averages.idxmin()

            peak_value = monthly_averages.max()
            lowest_value = monthly_averages.min()

            # Simple seasonality check: peak is significantly higher than lowest
            is_seasonal = peak_value > lowest_value * 1.5 if lowest_value > 0 else peak_value > 10 # Threshold if lowest is 0 or negative

            # Convert month numbers to names
            month_names = ["", "January", "February", "March", "April", "May", "June",
                           "July", "August", "September", "October", "November", "December"]

            final_result = {
                "is_seasonal": is_seasonal,
                "peak_month": month_names[peak_month_num],
                "peak_value": round(peak_value, 2),
                "lowest_month": month_names[lowest_month_num],
                "lowest_value": round(lowest_value, 2),
                "monthly_averages": {month_names[m]: round(v, 2) for m, v in monthly_averages.items()}
            }
            logger.debug(f"Seasonality analysis result: {final_result}")
            return final_result
        except Exception as e:
            logger.exception(f"Error during seasonality analysis: {e}")
            default_result["reason"] = f"Error during seasonality analysis: {e}"
            return default_result
