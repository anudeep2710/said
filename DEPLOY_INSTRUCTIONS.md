# 🚀 Quick Deployment Instructions for TalkToYourDocument

## Project: said-eb2f5

### Prerequisites

1. **Install Google Cloud SDK** (if not already installed):
   - Download from: https://cloud.google.com/sdk/docs/install
   - Run the installer and follow the setup wizard

2. **Authenticate with Google Cloud**:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

3. **Set your project**:
   ```bash
   gcloud config set project said-eb2f5
   ```

### Option 1: Automated Deployment (Recommended)

**For Windows PowerShell:**
```powershell
.\deploy.ps1
```

**For Linux/Mac:**
```bash
chmod +x deploy.sh
./deploy.sh
```

### Option 2: Manual Step-by-Step Deployment

1. **Enable required APIs**:
   ```bash
   gcloud services enable cloudbuild.googleapis.com
   gcloud services enable run.googleapis.com
   gcloud services enable storage.googleapis.com
   gcloud services enable aiplatform.googleapis.com
   ```

2. **Create storage bucket**:
   ```bash
   gsutil mb -p said-eb2f5 -c STANDARD -l us-central1 gs://said-eb2f5-documents/
   ```

3. **Build and deploy**:
   ```bash
   # Build the container
   gcloud builds submit --tag gcr.io/said-eb2f5/talktoyourdocument

   # Deploy to Cloud Run
   gcloud run deploy talktoyourdocument \
     --image gcr.io/said-eb2f5/talktoyourdocument \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --memory 2Gi \
     --cpu 2 \
     --timeout 300 \
     --max-instances 10 \
     --set-env-vars "GOOGLE_CLOUD_PROJECT=said-eb2f5,GOOGLE_CLOUD_LOCATION=us-central1,GCS_BUCKET_NAME=said-eb2f5-documents,USE_MOCK_STORAGE=false"
   ```

### After Deployment

1. **Get your service URL**:
   ```bash
   gcloud run services describe talktoyourdocument --platform managed --region us-central1 --format 'value(status.url)'
   ```

2. **Test the API**:
   - Health check: `https://your-service-url/`
   - API docs: `https://your-service-url/docs`
   - Upload test: Use the `/upload` endpoint

### Expected Deployment Time
- **First deployment**: 5-10 minutes
- **Subsequent deployments**: 2-5 minutes

### Troubleshooting

**If deployment fails:**
1. Check Cloud Build logs: `gcloud builds log --limit=1`
2. Verify project permissions
3. Ensure billing is enabled on the project

**If service doesn't respond:**
1. Check Cloud Run logs: `gcloud logs tail "resource.type=cloud_run_revision"`
2. Verify environment variables are set correctly

### Cost Estimate
- **Cloud Run**: ~$0.10-$1.00 per day (depending on usage)
- **Cloud Storage**: ~$0.02 per GB per month
- **Cloud Build**: First 120 build-minutes per day are free

### Security Note
The service is deployed with public access for testing. For production, consider adding authentication.

---

**Ready to deploy?** Run the deployment script and your TalkToYourDocument API will be live on Google Cloud! 🎉
