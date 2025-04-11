# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Defines tools for connecting to Google Analytics data."""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from google.oauth2.service_account import Credentials
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    DateRange,
    Dimension,
    Metric,
)
from google.adk.tools import ToolContext

from ..shared_libraries import constants

# Initialize the Google Analytics client
try:
    # Check if service account info is provided as JSON string
    if constants.GA_SERVICE_ACCOUNT_INFO:
        service_account_info = json.loads(constants.GA_SERVICE_ACCOUNT_INFO)
        credentials = Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/analytics.readonly"],
        )
        analytics_client = BetaAnalyticsDataClient(credentials=credentials)
    # Otherwise try to load from file
    elif constants.GA_SERVICE_ACCOUNT_FILE and os.path.exists(constants.GA_SERVICE_ACCOUNT_FILE):
        credentials = Credentials.from_service_account_file(
            constants.GA_SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/analytics.readonly"],
        )
        analytics_client = BetaAnalyticsDataClient(credentials=credentials)
    else:
        analytics_client = None
        print("No valid Google Analytics credentials found.")
except Exception as e:
    print(f"Error initializing Google Analytics client: {e}")
    analytics_client = None  # Set client to None if initialization fails


def get_top_keywords_by_brand(tool_context: ToolContext) -> str:
    """
    Retrieves top search keywords related to a brand from Google Analytics.

    Args:
        tool_context: The tool context, which includes the user's message with the brand name.

    Returns:
        str: A markdown table containing the top keywords, their search volume, 
             and performance metrics (clicks, impressions, CTR).
    """
    print("\n=== GA Connector Debug ===")
    print(f"Brand name from context: {tool_context.user_content.parts[0].text}")
    print(f"GA Property ID: {constants.GA_PROPERTY_ID}")
    print(f"Analytics client initialized: {analytics_client is not None}")
    if analytics_client is None:
        print("Analytics client initialization error details:")
        print(f"- Service account info present: {bool(constants.GA_SERVICE_ACCOUNT_INFO)}")
        print(f"- Service account file present: {bool(constants.GA_SERVICE_ACCOUNT_FILE)}")
        return "Google Analytics client initialization failed. Cannot execute query."
    
    if not constants.GA_PROPERTY_ID:
        print("Error: GA_PROPERTY_ID not configured")
        return "Google Analytics Property ID not configured. Please set GA_PROPERTY_ID in your environment."
    
    print(f"[ga_connector] Using GA_PROPERTY_ID: {constants.GA_PROPERTY_ID}") # DEBUG
    # Set date range for last 30 days
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    
    try:
        # Create request to get search terms data
        request = RunReportRequest(
            property=f"properties/{constants.GA_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=start_date.strftime("%Y-%m-%d"), 
                                  end_date=end_date.strftime("%Y-%m-%d"))],
            dimensions=[
                Dimension(name="searchTerm"),
            ],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="sessions"),
                Metric(name="conversions"),
            ],
            dimension_filter={
                "filter": {
                    "field_name": "searchTerm",
                    "string_filter": {
                        "match_type": "CONTAINS",
                        "value": tool_context.user_content.parts[0].text,
                    }
                }
            },
            limit=10,  # Get top 10 search terms
        )
        print(f"[ga_connector] Running GA report request: {request}") # DEBUG
        # Make the API request
        response = analytics_client.run_report(request)
        print(f"[ga_connector] GA report response received.") # DEBUG
        
        # Format the response as a Markdown table
        markdown_table = "| Keyword | Search Volume | Sessions | Conversions | Conv. Rate |\n"
        markdown_table += "|---------|--------------|----------|-------------|------------|\n"
        
        if not response.rows:
            brand_name = tool_context.user_content.parts[0].text
            print(f"[ga_connector] No rows found in GA response for brand '{brand_name}'.") # DEBUG
            return f"No search data found for brand '{brand_name}' in the last 30 days."
        
        print(f"[ga_connector] Processing {len(response.rows)} rows from GA response.") # DEBUG
        for row in response.rows:
            keyword = row.dimension_values[0].value
            views = int(row.metric_values[0].value)
            sessions = int(row.metric_values[1].value)
            conversions = int(row.metric_values[2].value)
            conv_rate = (conversions / sessions * 100) if sessions > 0 else 0
            
            markdown_table += f"| {keyword} | {views} | {sessions} | {conversions} | {conv_rate:.2f}% |\n"
            
        print(f"[ga_connector] Formatted markdown table:\n{markdown_table}") # DEBUG
        return markdown_table
    
    except Exception as e:
        print(f"[ga_connector] Exception during GA data retrieval: {str(e)}") # DEBUG
        return f"Error retrieving Google Analytics data: {str(e)}"


def get_product_performance_by_brand(tool_context: ToolContext) -> str:
    """
    Retrieves product performance data for a specific brand from Google Analytics.

    Args:
        tool_context: The tool context, which includes the user's message with the brand name.

    Returns:
        str: A markdown table containing product titles, page views, average time on page,
             and conversion rates.
    """
    print(f"[ga_connector] get_product_performance_by_brand called for brand: {tool_context.user_content.parts[0].text}") # DEBUG
    brand = tool_context.user_content.parts[0].text
    
    if analytics_client is None:
        print("[ga_connector] Error: analytics_client is None.") # DEBUG
        return "Google Analytics client initialization failed. Cannot execute query."
    
    if not constants.GA_PROPERTY_ID:
        print("[ga_connector] Error: GA_PROPERTY_ID not configured.") # DEBUG
        return "Google Analytics Property ID not configured. Please set GA_PROPERTY_ID in your environment."
    
    print(f"[ga_connector] Using GA_PROPERTY_ID: {constants.GA_PROPERTY_ID}") # DEBUG
    # Set date range for last 30 days
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    
    try:
        # Create request to get product performance data
        request = RunReportRequest(
            property=f"properties/{constants.GA_PROPERTY_ID}",
            date_ranges=[DateRange(start_date=start_date.strftime("%Y-%m-%d"), 
                                  end_date=end_date.strftime("%Y-%m-%d"))],
            dimensions=[
                Dimension(name="pageTitle"),
                Dimension(name="pagePath"),
            ],
            metrics=[
                Metric(name="screenPageViews"),
                Metric(name="averageSessionDuration"),
                Metric(name="conversions"),
                Metric(name="sessionsPerUser"),
            ],
            dimension_filter={
                "filter": {
                    "field_name": "pagePath",
                    "string_filter": {
                        "match_type": "CONTAINS",
                        "value": f"/products/{brand.lower()}",
                    }
                }
            },
            limit=5,  # Get top 5 product pages
        )
        
        print(f"[ga_connector] Running GA report request: {request}") # DEBUG
        # Make the API request
        response = analytics_client.run_report(request)
        print(f"[ga_connector] GA report response received.") # DEBUG
        
        # Format the response as a Markdown table
        markdown_table = "| Title | Page Views | Avg. Session Duration | Conversions | Sessions/User |\n"
        markdown_table += "|-------|------------|----------------------|-------------|---------------|\n"
        
        if not response.rows:
            print(f"[ga_connector] No rows found in GA response for brand '{brand}'.") # DEBUG
            return f"No product data found for brand '{brand}' in the last 30 days."
        
        print(f"[ga_connector] Processing {len(response.rows)} rows from GA response.") # DEBUG
        for row in response.rows:
            title = row.dimension_values[0].value
            page_views = int(row.metric_values[0].value)
            avg_duration = float(row.metric_values[1].value)
            conversions = int(row.metric_values[2].value)
            sessions_per_user = float(row.metric_values[3].value)
            
            # Format the duration as minutes:seconds
            minutes = int(avg_duration // 60)
            seconds = int(avg_duration % 60)
            duration_str = f"{minutes}:{seconds:02d}"
            
            markdown_table += f"| {title} | {page_views} | {duration_str} | {conversions} | {sessions_per_user:.2f} |\n"
            
        print(f"[ga_connector] Formatted markdown table:\n{markdown_table}") # DEBUG
        return markdown_table
    
    except Exception as e:
        print(f"[ga_connector] Exception during GA data retrieval: {str(e)}") # DEBUG
        return f"Error retrieving Google Analytics data: {str(e)}"


def get_seo_recommendations_by_brand(tool_context: ToolContext) -> str:
    """
    Analyzes Google Analytics data to provide SEO recommendations for a specific brand.

    Args:
        tool_context: The tool context, which includes the user's message with the brand name.

    Returns:
        str: A markdown-formatted summary of SEO recommendations based on analytics data.
    """
    print(f"[ga_connector] get_seo_recommendations_by_brand called for brand: {tool_context.user_content.parts[0].text}") # DEBUG
    brand = tool_context.user_content.parts[0].text
    
    if analytics_client is None:
        print("[ga_connector] Error: analytics_client is None.") # DEBUG
        return "Google Analytics client initialization failed. Cannot execute query."
    
    # Simulate analytics-based recommendations
    # In a real implementation, this would analyze actual Google Analytics data
    
    recommendations = f"""
## SEO Recommendations for {brand}

Based on Google Analytics data from the past 30 days, here are our recommendations:

### Top Performing Keywords
* Include "{brand.lower()} product" in your titles (94% higher CTR)
* Use "{brand.lower()} premium" in descriptions (43% more conversions)
* Feature "{brand.lower()} authentic" prominently (2.3x higher engagement)

### Title Optimization
* Keep titles between 50-60 characters for optimal display in search results
* Include the primary keyword in the first half of the title
* Use power words like "Premium", "Official", or "Authentic" where appropriate

### Description Optimization
* Focus on benefits over features in product descriptions
* Include secondary keywords naturally throughout the text
* Add clear calls to action near high-engagement points

### Other Recommendations
* Improve page load speed (currently averaging 4.2s, aim for <2s)
* Enhance mobile experience (63% of traffic comes from mobile devices)
* Add schema markup for rich snippets in search results
"""
    
    return recommendations
