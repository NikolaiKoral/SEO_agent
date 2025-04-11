# Important Note About Google Analytics API Access

## Using Service Accounts Instead of Direct Login Credentials

I notice you've shared direct login credentials for Google Analytics (username/password). However, the Google Analytics API doesn't support this type of authentication. Instead, it requires a service account with appropriate permissions.

## Steps to Create a Service Account

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one (e.g., `its-koral-prod`)
3. **Enable the Google Analytics Data API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Analytics Data API"
   - Click on it and then click "Enable"
4. Go to "IAM & Admin" > "Service Accounts"
5. Click "Create Service Account"
6. Provide a name and description
7. Grant the following roles:
   - `roles/analyticsadmin.reader`
   - `roles/analytics.viewer`
8. Create a key for this service account (JSON format)
9. Download the JSON key file

## Linking the Service Account to Your Google Analytics Property

1. Go to your Google Analytics Admin page
2. Select the property (287599719)
3. Under "  roperty" column, click "Property Access Management"
4. Click the "+ Add" button
5. Add the service account email address (it will look like: `service-account-name@project-id.iam.gserviceaccount.com`)
6. Give it "Read & Analyze" permissions

## Update the .env Configuration

Once you have the service account key file, you can update the .env file with:

```
GA_PROPERTY_ID="287599719"
GA_SERVICE_ACCOUNT_FILE="/path/to/your/downloaded-key-file.json"
```

Alternatively, you can copy the entire content of the JSON key file and set it as:

```
GA_SERVICE_ACCOUNT_INFO='{"type":"service_account","project_id":"your-project-id",...}'
```

## Important Security Note

Service accounts are the secure, recommended way to access the Google Analytics API programmatically. Never share your service account keys publicly, and consider using environment variables or secret management systems in production environments.
