import os
import json # Added for potential error parsing
import logging # Added import
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


class MerchantCenterInput(TypedDict):
    product_id: str # Merchant Center product ID (often 'online:en:DK:{EAN}' or similar)
    category: Optional[str]
    days: Optional[int] # Used for mocked performance report

class MerchantCenterTool(BaseTool):
    """Tool for retrieving data from Google Merchant Center"""

    def __init__(self, config=None):
        self.config = config or {}
        self.credentials_path = self.config.get("MERCHANT_CENTER_CREDENTIALS") or os.environ.get("MERCHANT_CENTER_CREDENTIALS")
        self.merchant_id = self.config.get("MERCHANT_CENTER_ID") or os.environ.get("MERCHANT_CENTER_ID")
        self.client = self._initialize_client()
        if self.client:
            logger.info("Merchant Center client initialized successfully.")
        else:
            logger.error("Merchant Center client failed to initialize.")

    def _initialize_client(self):
        """Initialize Merchant Center API client"""
        if not self.credentials_path or not os.path.exists(self.credentials_path):
            logger.error(f"Merchant Center credentials path not found or invalid: {self.credentials_path}")
            return None
        if not self.merchant_id:
            logger.error("Merchant Center ID (MERCHANT_CENTER_ID) not configured.")
            return None

        try:
            logger.debug(f"Initializing Merchant Center client with credentials: {self.credentials_path} for merchant: {self.merchant_id}")
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/content']
            )
            # Use content API v2.1
            return build('content', 'v2.1', credentials=credentials)
        except Exception as e:
            logger.exception(f"Error initializing Merchant Center client: {e}")
            return None

    async def invoke(self, args: MerchantCenterInput) -> Dict[str, Any]:
        """Invoke the Merchant Center tool"""
        logger.info(f"Invoking MerchantCenterTool with args: {args}")
        if not self.client:
            logger.error("Merchant Center client not initialized, cannot invoke tool.")
            return {"error": "Merchant Center client not initialized"}

        product_id = args.get("product_id")
        category = args.get("category") # Used for mocked price insights
        days = args.get("days", 30) # Used for mocked performance report

        if not product_id:
            logger.error("Missing required argument: product_id")
            return {"error": "product_id is required"}

        results = {}
        errors = {} # Collect errors from different parts

        # Get product data
        product_data_result = self._get_product_data(product_id)
        if "error" in product_data_result:
            errors["product_data_error"] = product_data_result["error"]
        else:
            results["product_data"] = product_data_result

        # Get product issues
        product_issues_result = self._get_product_issues(product_id)
        if "error" in product_issues_result:
            errors["product_issues_error"] = product_issues_result["error"]
        else:
            results["product_issues"] = product_issues_result

        # Get performance report (Mocked for now, requires Performance Reports API)
        # No real API call, so less error handling needed here for now
        results["performance_report"] = self._get_performance_report(product_id, days)

        # Get price insights (Mocked for now, requires Price Competitiveness API)
        # No real API call, so less error handling needed here for now
        results["price_insights"] = self._get_competitor_price_insights(product_id, category)

        if errors:
            logger.warning(f"MerchantCenterTool invocation finished with errors: {errors}")
            results["errors"] = errors # Include collected errors in the final result

        logger.info(f"MerchantCenterTool invocation finished. Returning keys: {list(results.keys())}")
        return results # Return results even if some parts failed

    def _get_product_data(self, product_id):
        """Get product data from Merchant Center"""
        logger.info(f"Fetching product data for product_id: {product_id}")
        try:
            # Note: product_id format is crucial, e.g., 'online:en:DK:1234567890123'
            logger.debug(f"Executing products().get() for merchantId: {self.merchant_id}, productId: {product_id}")
            response = self.client.products().get(
                merchantId=self.merchant_id,
                productId=product_id
            ).execute()
            logger.info(f"Successfully retrieved product data for {product_id}")
            return response
        except Exception as e:
            error_message = f"Error getting product data for {product_id}: {e}"
            error_details = str(e)
            # Check for specific Google API errors
            if GoogleHttpError and isinstance(e, GoogleHttpError):
                 try:
                     # Attempt to parse error details
                     error_content = json.loads(e.content).get('error', {})
                     error_message = f"Google API Error getting product data: {error_content.get('message', str(e))}"
                     if error_content.get('code') == 404:
                         error_message = f"Product not found in Merchant Center: {product_id}"
                         logger.warning(error_message)
                         return {"error": error_message} # Return specific error for not found
                 except:
                     error_message = f"Google API Error getting product data: {e}" # Fallback

            logger.exception(error_message)
            return {"error": error_message, "details": error_details}

    def _get_product_issues(self, product_id):
        """Get product data quality issues"""
        logger.info(f"Fetching product issues for product_id: {product_id}")
        try:
            logger.debug(f"Executing productstatuses().get() for merchantId: {self.merchant_id}, productId: {product_id}")
            response = self.client.productstatuses().get(
                 merchantId=self.merchant_id,
                 productId=product_id
            ).execute()
            logger.info(f"Successfully retrieved product status for {product_id}")
            return self._process_product_issues(response)
        except Exception as e:
            error_message = f"Error getting product issues for {product_id}: {e}"
            error_details = str(e)
            if GoogleHttpError and isinstance(e, GoogleHttpError):
                 try:
                     error_content = json.loads(e.content).get('error', {})
                     error_message = f"Google API Error getting product issues: {error_content.get('message', str(e))}"
                     if error_content.get('code') == 404:
                         error_message = f"Product status not found in Merchant Center: {product_id}"
                         logger.warning(error_message)
                         # It's okay if status isn't found, might just mean no issues or not processed yet
                         # Return an empty success structure instead of error
                         return {"has_critical_issues": False, "issue_count": 0, "issues": []}
                 except:
                     error_message = f"Google API Error getting product issues: {e}" # Fallback

            logger.exception(error_message)
            return {"error": error_message, "details": error_details}

    def _process_product_issues(self, response):
        """Process product issues response"""
        logger.debug("Processing product issues response.")
        issues = []
        has_critical_issues = False

        item_level_issues = response.get('itemLevelIssues', [])
        if not item_level_issues:
            logger.info("No item level issues found in product status response.")

        for issue in item_level_issues:
            severity = issue.get('severity')
            code = issue.get('code')
            description = issue.get('description')
            attribute = issue.get('attributeName', 'N/A') # Correct field name
            documentation = issue.get('documentation', 'N/A')

            logger.debug(f"Found issue: code={code}, severity={severity}, attribute={attribute}, desc={description}")

            if severity in ['error', 'critical']:
                has_critical_issues = True

            issues.append({
                "code": code,
                "severity": severity,
                "description": description,
                "attribute": attribute,
                "documentation": documentation
            })

        # Sort issues by severity (critical > error > warning > info)
        severity_order = {'critical': 0, 'error': 1, 'warning': 2, 'info': 3}
        issues.sort(key=lambda x: severity_order.get(x.get('severity'), 4))

        processed_issues = {
            "has_critical_issues": has_critical_issues,
            "issue_count": len(issues),
            "issues": issues
        }
        logger.debug(f"Finished processing product issues. Found {len(issues)} issues. Has critical: {has_critical_issues}")
        return processed_issues

    def _get_performance_report(self, product_id, days):
        """Get Shopping performance report (Mocked)"""
        # Requires Performance Reports API access which is separate
        # Returning mock data structure
        logger.warning(f"Merchant Center performance report is mocked for product {product_id}")
        # Simple hash-based mock data generation
        impressions_mock = 1000 + hash(product_id) % 5000
        clicks_mock = 50 + hash(product_id) % 200
        conversions_mock = 5 + hash(product_id) % 50
        ctr_mock = round((clicks_mock / impressions_mock * 100.0) if impressions_mock > 0 else 0.0, 2)
        conv_rate_mock = round((conversions_mock / clicks_mock * 100.0) if clicks_mock > 0 else 0.0, 2)

        return {
            "product_id": product_id,
            "metrics": {
                "impressions": impressions_mock,
                "clicks": clicks_mock,
                "ctr": ctr_mock,
                "conversions": conversions_mock,
                "conversion_rate": conv_rate_mock,
            },
            "benchmarks": { # Mock benchmarks
                "category_avg_ctr": 3.5,
                "category_avg_conversion_rate": 10.0,
            },
            "search_term_insights": [ # Mock search terms
                 {"term": f"mock term {hash(product_id)%10}", "impressions": 100, "clicks": 10, "conversions": 2},
                 {"term": f"another mock {hash(product_id)%20}", "impressions": 80, "clicks": 5, "conversions": 1},
            ]
        }

    def _get_competitor_price_insights(self, product_id, category):
        """Get competitive price insights (Mocked)"""
        # Requires Price Competitiveness API access which is separate
        # Returning mock data structure
        logger.warning(f"Merchant Center price insights are mocked for product {product_id}")
        mock_price = 80.0 + hash(product_id) % 40
        mock_benchmark = 75.0 + hash(category or product_id) % 30
        price_diff_percent = round(((mock_price - mock_benchmark) / mock_benchmark) * 100.0 if mock_benchmark > 0 else 0.0, 1)
        relative_pos = "above_average" if mock_price > mock_benchmark * 1.1 else "below_average" if mock_price < mock_benchmark * 0.9 else "average"

        return {
            "product_id": product_id,
            "price_competitiveness": {
                "price_benchmark": round(mock_benchmark, 2),
                "product_price": round(mock_price, 2),
                "price_difference_percentage": price_diff_percent,
                "relative_position": relative_pos
            },
            "category_price_range": { # Mock range
                "min": round(mock_benchmark * 0.8, 2),
                "max": round(mock_benchmark * 1.5, 2),
                "median": round(mock_benchmark, 2)
            }
        }
