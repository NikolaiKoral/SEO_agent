import os
from typing import Dict, Any, TypedDict, Optional, List
import pandas as pd # pytrends returns pandas DataFrames

# Need to handle potential import error if pytrends is not installed
try:
    from pytrends.request import TrendReq
except ImportError:
    TrendReq = None 

from a2a.tools import BaseTool

class GoogleTrendsInput(TypedDict):
    keyword: str
    timeframe: Optional[str] # e.g., 'today 12-m', 'today 3-m', 'now 7-d'
    geo: Optional[str] # e.g., 'US', 'DK', '' for worldwide

class GoogleTrendsTool(BaseTool):
    """Tool for retrieving data from Google Trends"""
    
    def __init__(self, config=None):
        self.config = config or {}
        if TrendReq is None:
            print("Warning: pytrends package not found. Google Trends tool will be disabled.")
            self.pytrends = None
        else:
            # Initialize pytrends client
            # Consider adding parameters for hl (language) and tz (timezone) if needed
            self.pytrends = TrendReq(hl='en-US', tz=360) 
    
    async def invoke(self, args: GoogleTrendsInput) -> Dict[str, Any]:
        """Invoke the Google Trends tool"""
        if not self.pytrends:
            return {"error": "pytrends package not installed or TrendReq failed to initialize"}
            
        keyword = args.get("keyword")
        timeframe = args.get("timeframe", 'today 12-m') # Default to last 12 months
        geo = args.get("geo", '') # Default to worldwide
        
        if not keyword:
            return {"error": "Keyword is required"}

        try:
            # Build the payload
            self.pytrends.build_payload([keyword], cat=0, timeframe=timeframe, geo=geo, gprop='')
            
            # Get interest over time
            interest_over_time_df = self.pytrends.interest_over_time()
            
            # Get related topics and queries
            # Note: related_topics() and related_queries() can sometimes fail or return empty
            related_topics_dict = {}
            related_queries_dict = {}
            try:
                 related_topics_dict = self.pytrends.related_topics()
            except Exception as e:
                 print(f"Warning: Could not fetch related topics for '{keyword}': {e}")
            try:
                 related_queries_dict = self.pytrends.related_queries()
            except Exception as e:
                 print(f"Warning: Could not fetch related queries for '{keyword}': {e}")


            # Format the response
            trend_data = {
                "interest_over_time": self._format_interest_data(interest_over_time_df, keyword),
                "related_topics": self._extract_related_data(related_topics_dict.get(keyword, {})),
                "related_queries": self._extract_related_data(related_queries_dict.get(keyword, {})),
                "is_rising": self._determine_if_rising(interest_over_time_df, keyword),
                "seasonality": self._analyze_seasonality(interest_over_time_df, keyword),
            }
            
            return trend_data

        except Exception as e:
            # Catch potential exceptions from pytrends (e.g., rate limits, request errors)
            return {"error": f"Error getting Google Trends data for '{keyword}': {e}"}

    def _format_interest_data(self, interest_df, keyword):
        """Format interest over time data"""
        if interest_df.empty or keyword not in interest_df.columns:
            return []
            
        # Convert DataFrame to list of dictionaries
        interest_data = []
        # Ensure 'isPartial' column exists, default to False if not
        if 'isPartial' not in interest_df.columns:
             interest_df['isPartial'] = False # Add default value

        for index, row in interest_df.iterrows():
            interest_data.append({
                "date": index.strftime("%Y-%m-%d"),
                "value": int(row[keyword]),
                "is_partial": bool(row['isPartial']) # Include partial data flag
            })
            
        return interest_data

    def _extract_related_data(self, related_data):
        """Extract related topics or queries"""
        rising = []
        top = []
        
        # Check if related_data is a dictionary and has the expected keys
        if isinstance(related_data, dict):
            rising_df = related_data.get('rising')
            top_df = related_data.get('top')

            # Convert DataFrames to dictionaries if they exist and are not None
            if isinstance(rising_df, pd.DataFrame) and not rising_df.empty:
                rising = rising_df.to_dict('records')
            
            if isinstance(top_df, pd.DataFrame) and not top_df.empty:
                top = top_df.to_dict('records')
        
        return {"rising": rising, "top": top}

    def _determine_if_rising(self, interest_df, keyword):
        """Determine if keyword interest is rising"""
        if interest_df.empty or keyword not in interest_df.columns or len(interest_df) < 4:
            return False
            
        values = interest_df[keyword].tolist()
        
        # Simple check: compare last value to average of first few values
        # More robust methods could involve regression or time series analysis
        if len(values) > 10:
             last_value = values[-1]
             avg_first_half = sum(values[:len(values)//2]) / (len(values)//2)
             # Consider rising if last value is > 20% above the first half average
             return last_value > avg_first_half * 1.2 
        return False # Not enough data for a simple trend check

    def _analyze_seasonality(self, interest_df, keyword):
        """Analyze seasonality patterns"""
        if interest_df.empty or keyword not in interest_df.columns or len(interest_df) < 12: # Need at least a year of data
            return {"is_seasonal": False, "reason": "Insufficient data"}
            
        try:
            # Group by month
            monthly_averages = interest_df.groupby(interest_df.index.month)[keyword].mean()
            
            if len(monthly_averages) < 12:
                 return {"is_seasonal": False, "reason": "Data does not cover full year"}

            # Find peak and lowest months
            peak_month_num = monthly_averages.idxmax()
            lowest_month_num = monthly_averages.idxmin()
            
            peak_value = monthly_averages.max()
            lowest_value = monthly_averages.min()
            
            # Simple seasonality check: peak is significantly higher than lowest
            is_seasonal = peak_value > lowest_value * 1.5 if lowest_value > 0 else peak_value > 10 # Threshold if lowest is 0
            
            # Convert month numbers to names
            month_names = ["", "January", "February", "March", "April", "May", "June", 
                           "July", "August", "September", "October", "November", "December"]
            
            return {
                "is_seasonal": is_seasonal,
                "peak_month": month_names[peak_month_num],
                "peak_value": round(peak_value, 2),
                "lowest_month": month_names[lowest_month_num],
                "lowest_value": round(lowest_value, 2),
                "monthly_averages": {month_names[m]: round(v, 2) for m, v in monthly_averages.items()}
            }
        except Exception as e:
            return {"is_seasonal": False, "reason": f"Error during seasonality analysis: {e}"}
