# TalkToYourDocument - Google Cloud Deployment Guide

## Prerequisites

1. **Google Cloud SDK**: Install and configure the Google Cloud SDK
   ```bash
   # Install gcloud CLI
   curl https://sdk.cloud.google.com | bash
   exec -l $SHELL
   gcloud init
   ```

2. **Authentication**: Authenticate with Google Cloud
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

3. **Project Setup**: Set your project ID
   ```bash
   gcloud config set project said-eb2f5
   ```

## Quick Deployment

### Option 1: Automated Deployment Script

1. Make the deployment script executable:
   ```bash
   chmod +x deploy.sh
   ```

2. Run the deployment:
   ```bash
   ./deploy.sh
   ```

### Option 2: Manual Deployment Steps

1. **Enable Required APIs**:
   ```bash
   gcloud services enable cloudbuild.googleapis.com
   gcloud services enable run.googleapis.com
   gcloud services enable storage.googleapis.com
   gcloud services enable aiplatform.googleapis.com
   ```

2. **Create Cloud Storage Bucket**:
   ```bash
   gsutil mb -p said-eb2f5 -c STANDARD -l us-central1 gs://said-eb2f5-documents/
   ```

3. **Build and Deploy**:
   ```bash
   # Build the image
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

### Option 3: Cloud Build Trigger

1. **Create a trigger**:
   ```bash
   gcloud builds triggers create github \
     --repo-name=TalkToYourDocument \
     --repo-owner=yourusername \
     --branch-pattern="^main$" \
     --build-config=cloudbuild.yaml
   ```

## Configuration

### Environment Variables

The application uses these environment variables:

- `GOOGLE_CLOUD_PROJECT`: Your Google Cloud project ID (said-eb2f5)
- `GOOGLE_CLOUD_LOCATION`: Deployment region (us-central1)
- `GCS_BUCKET_NAME`: Cloud Storage bucket name (said-eb2f5-documents)
- `USE_MOCK_STORAGE`: Set to "false" for production

### Required Permissions

Ensure your Cloud Run service has these IAM roles:
- Storage Object Admin (for document storage)
- Vertex AI User (for Gemma model access)

## Post-Deployment

### 1. Get Service URL
```bash
gcloud run services describe talktoyourdocument \
  --platform managed \
  --region us-central1 \
  --format 'value(status.url)'
```

### 2. Test the Deployment
```bash
# Health check
curl https://your-service-url/

# API documentation
open https://your-service-url/docs
```

### 3. Upload a Test Document
```bash
curl -X POST \
  -F "file=@your-document.pdf" \
  https://your-service-url/upload
```

## Monitoring and Logs

### View Logs
```bash
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=talktoyourdocument" --limit 50
```

### Monitor Performance
- Visit Google Cloud Console > Cloud Run > talktoyourdocument
- Check metrics for CPU, memory, and request latency

## Scaling Configuration

The deployment is configured with:
- **Memory**: 2GB
- **CPU**: 2 vCPUs
- **Timeout**: 300 seconds
- **Max Instances**: 10
- **Concurrency**: 80 requests per instance

## Security

- The service allows unauthenticated access for testing
- For production, consider adding authentication:
  ```bash
  gcloud run services remove-iam-policy-binding talktoyourdocument \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --region=us-central1
  ```

## Troubleshooting

### Common Issues

1. **Build Failures**: Check Cloud Build logs
2. **Storage Errors**: Verify bucket permissions
3. **Memory Issues**: Increase memory allocation
4. **Timeout Issues**: Increase timeout or optimize code

### Debug Commands
```bash
# Check service status
gcloud run services describe talktoyourdocument --region=us-central1

# View recent logs
gcloud logs tail "resource.type=cloud_run_revision"

# Test locally with production settings
docker build -t talktoyourdocument .
docker run -p 8080:8080 -e USE_MOCK_STORAGE=true talktoyourdocument
```

## Cost Optimization

- Cloud Run charges only for actual usage
- Consider setting up budget alerts
- Monitor storage costs in Cloud Storage

## Next Steps

1. Set up CI/CD pipeline
2. Add authentication and authorization
3. Implement monitoring and alerting
4. Configure custom domain
5. Set up SSL certificates
