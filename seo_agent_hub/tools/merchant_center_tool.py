import os
from typing import Dict, Any, TypedDict, Optional, List

from a2a.tools import BaseTool
from google.oauth2 import service_account
from googleapiclient.discovery import build

class MerchantCenterInput(TypedDict):
    product_id: str # Merchant Center product ID (often 'online:en:DK:{EAN}' or similar)
    category: Optional[str]
    days: Optional[int]

class MerchantCenterTool(BaseTool):
    """Tool for retrieving data from Google Merchant Center"""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.credentials_path = self.config.get("MERCHANT_CENTER_CREDENTIALS") or os.environ.get("MERCHANT_CENTER_CREDENTIALS")
        self.merchant_id = self.config.get("MERCHANT_CENTER_ID") or os.environ.get("MERCHANT_CENTER_ID")
        self.client = self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Merchant Center API client"""
        if not self.credentials_path or not os.path.exists(self.credentials_path):
            print("Merchant Center credentials path not found or not configured.")
            return None
        if not self.merchant_id:
            print("Merchant Center ID not configured.")
            return None
            
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/content']
            )
            # Use content API v2.1
            return build('content', 'v2.1', credentials=credentials)
        except Exception as e:
            print(f"Error initializing Merchant Center client: {e}")
            return None

    async def invoke(self, args: MerchantCenterInput) -> Dict[str, Any]:
        """Invoke the Merchant Center tool"""
        if not self.client:
            return {"error": "Merchant Center client not initialized"}
            
        product_id = args.get("product_id")
        category = args.get("category")
        days = args.get("days", 30) # Default to 30 days for performance
        
        if not product_id:
            return {"error": "product_id is required"}

        results = {}
        try:
            # Get product data
            results["product_data"] = self._get_product_data(product_id)
            
            # Get product issues
            results["product_issues"] = self._get_product_issues(product_id)
            
            # Get performance report (Mocked for now, requires Performance Reports API)
            results["performance_report"] = self._get_performance_report(product_id, days)
            
            # Get price insights (Mocked for now, requires Price Competitiveness API)
            results["price_insights"] = self._get_competitor_price_insights(product_id, category)

            return results

        except Exception as e:
            return {"error": f"Error getting Merchant Center data: {e}"}

    def _get_product_data(self, product_id):
        """Get product data from Merchant Center"""
        try:
            # Note: product_id format is crucial, e.g., 'online:en:DK:1234567890123'
            response = self.client.products().get(
                merchantId=self.merchant_id,
                productId=product_id
            ).execute()
            return response
        except Exception as e:
            print(f"Error getting product data for {product_id}: {e}")
            # Return specific error if product not found
            if "notFound" in str(e):
                 return {"error": f"Product not found in Merchant Center: {product_id}"}
            return {"error": f"API error getting product data: {str(e)}"}

    def _get_product_issues(self, product_id):
        """Get product data quality issues"""
        try:
            response = self.client.productstatuses().get(
                 merchantId=self.merchant_id,
                 productId=product_id
            ).execute()
            return self._process_product_issues(response)
        except Exception as e:
            print(f"Error getting product issues for {product_id}: {e}")
            if "notFound" in str(e):
                 return {"error": f"Product status not found in Merchant Center: {product_id}"}
            return {"error": f"API error getting product issues: {str(e)}"}

    def _process_product_issues(self, response):
        """Process product issues response"""
        issues = []
        has_issues = False
        
        item_level_issues = response.get('itemLevelIssues', [])
        for issue in item_level_issues:
            severity = issue.get('severity')
            if severity in ['error', 'critical']:
                has_issues = True
                
            issues.append({
                "code": issue.get('code'),
                "severity": severity,
                "description": issue.get('description'),
                "attribute": issue.get('attributeName', 'N/A'), # Correct field name
                "documentation": issue.get('documentation', 'N/A')
            })
            
        # Sort issues by severity (critical > error > warning > info)
        severity_order = {'critical': 0, 'error': 1, 'warning': 2, 'info': 3}
        issues.sort(key=lambda x: severity_order.get(x.get('severity'), 4))

        return {
            "has_critical_issues": has_issues,
            "issue_count": len(issues),
            "issues": issues
        }

    def _get_performance_report(self, product_id, days):
        """Get Shopping performance report (Mocked)"""
        # Requires Performance Reports API access which is separate
        # Returning mock data structure
        print(f"Note: Merchant Center performance report is mocked for product {product_id}")
        return {
            "product_id": product_id,
            "metrics": {
                "impressions": 1000 + hash(product_id) % 5000, # Mock data
                "clicks": 50 + hash(product_id) % 200,
                "ctr": round( (50 + hash(product_id) % 200) / (1000 + hash(product_id) % 5000) * 100 if (1000 + hash(product_id) % 5000) > 0 else 0, 2),
                "conversions": 5 + hash(product_id) % 50,
                "conversion_rate": round( (5 + hash(product_id) % 50) / (50 + hash(product_id) % 200) * 100 if (50 + hash(product_id) % 200) > 0 else 0, 2),
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
        print(f"Note: Merchant Center price insights are mocked for product {product_id}")
        mock_price = 80 + hash(product_id) % 40
        mock_benchmark = 75 + hash(category or product_id) % 30
        return {
            "product_id": product_id,
            "price_competitiveness": {
                "price_benchmark": round(mock_benchmark, 2),
                "product_price": round(mock_price, 2),
                "price_difference": round(((mock_price - mock_benchmark) / mock_benchmark) * 100 if mock_benchmark > 0 else 0, 1),
                "relative_position": "above_average" if mock_price > mock_benchmark * 1.1 else "below_average" if mock_price < mock_benchmark * 0.9 else "average"
            },
            "category_price_range": { # Mock range
                "min": round(mock_benchmark * 0.8, 2),
                "max": round(mock_benchmark * 1.5, 2),
                "median": round(mock_benchmark, 2)
            }
        }
