# Google Analytics Integration for Brand Search Optimization Agent

This document explains how to configure and use the Google Analytics integration for the Brand Search Optimization agent. This integration replaces the original BigQuery-based data source and leverages Google Analytics data for more accurate keyword and SEO recommendations.

## Overview

The Google Analytics integration provides the following capabilities:

1. **Keyword Analysis**: Retrieves top-performing search terms from your website related to a brand, including search volume, sessions, and conversion metrics.
2. **Product Performance Analysis**: Analyzes how product pages perform in terms of page views, session duration, and conversions.
3. **SEO Recommendations**: Generates data-driven SEO recommendations based on your Google Analytics data, helping optimize product titles and descriptions.

## Configuration

To use the Google Analytics integration, you need to:

1. Set up a Google Analytics 4 property for your website
2. Create a service account with appropriate permissions
3. Configure the agent with your Google Analytics credentials

### Step 1: Configuring the .env File

Edit the `.env` file to include your Google Analytics configuration:

```ini
# Google Analytics Configuration
GA_PROPERTY_ID="123456789"  # Your GA4 property ID (required)

# Option 1: Path to your service account key file
GA_SERVICE_ACCOUNT_FILE="/path/to/your/service-account-key.json"

# Option 2: Or provide service account info directly as a JSON string
# GA_SERVICE_ACCOUNT_INFO='{"type":"service_account","project_id":"your-project", ... }'
```

You must provide either `GA_SERVICE_ACCOUNT_FILE` or `GA_SERVICE_ACCOUNT_INFO`.

### Step 2: Creating a Service Account

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select an existing project
3. Navigate to "IAM & Admin" > "Service Accounts"
4. Click "Create Service Account"
5. Provide a name and description for the service account
6. Grant the following roles:
   - `roles/analyticsadmin.reader`
   - `roles/analytics.viewer`
7. Create a key for the service account (JSON format)
8. Download the JSON key file

### Step 3: Linking the Service Account to Google Analytics

1. Go to your Google Analytics Admin page
2. Click on "Account Access Management"
3. Add the service account email address with "Read & Analyze" permissions

## Using the Google Analytics Integration

With the integration properly configured, the agent will now:

1. Use `get_top_keywords_by_brand` to retrieve keyword data from Google Analytics
2. Use `get_product_performance_by_brand` to analyze product page performance
3. Use `get_seo_recommendations_by_brand` to generate SEO recommendations

The agent's workflow remains the same:

1. You provide a brand name
2. The keyword finding agent retrieves top keywords from Google Analytics
3. The comparison agent analyzes performance data and generates optimization recommendations

## Troubleshooting

If you encounter issues with the Google Analytics integration:

1. **Authentication Errors**: Verify that your service account has the correct permissions and has been properly linked to your Google Analytics property.
2. **No Data Found**: Make sure your GA4 property has adequate data history (at least 30 days recommended) and that the brand name you're searching for appears in your analytics data.
3. **API Quota Errors**: Google Analytics API has rate limits. If you're running many requests, you might hit these limits.

## Requirements

- Google Analytics 4 property with sufficient historical data
- Google Cloud project with the Analytics API enabled
- Service account with appropriate permissions
- Python 3.11+ and the dependencies in the `pyproject.toml` file
