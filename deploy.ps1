# PowerShell deployment script for Windows
# TalkToYourDocument - Google Cloud Run Deployment

# Configuration
$PROJECT_ID = "said-eb2f5"
$SERVICE_NAME = "talktoyourdocument"
$REGION = "us-central1"
$IMAGE_NAME = "gcr.io/$PROJECT_ID/$SERVICE_NAME"

Write-Host "🚀 Deploying TalkToYourDocument to Google Cloud Run" -ForegroundColor Green
Write-Host "Project ID: $PROJECT_ID" -ForegroundColor Cyan
Write-Host "Service Name: $SERVICE_NAME" -ForegroundColor Cyan
Write-Host "Region: $REGION" -ForegroundColor Cyan

# Check if gcloud is installed
try {
    $gcloudVersion = gcloud version 2>$null
    Write-Host "✅ Google Cloud SDK found" -ForegroundColor Green
} catch {
    Write-Host "❌ Google Cloud SDK not found. Please install it first." -ForegroundColor Red
    Write-Host "Download from: https://cloud.google.com/sdk/docs/install" -ForegroundColor Yellow
    exit 1
}

# Set the project
Write-Host "📋 Setting Google Cloud project..." -ForegroundColor Yellow
gcloud config set project $PROJECT_ID

# Enable required APIs
Write-Host "🔧 Enabling required Google Cloud APIs..." -ForegroundColor Yellow
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable aiplatform.googleapis.com

# Build and push the Docker image
Write-Host "🏗️ Building Docker image..." -ForegroundColor Yellow
gcloud builds submit --tag $IMAGE_NAME

# Create Cloud Storage bucket for documents
$BUCKET_NAME = "$PROJECT_ID-documents"
Write-Host "📦 Creating Cloud Storage bucket: $BUCKET_NAME" -ForegroundColor Yellow
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$BUCKET_NAME/ 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ℹ️ Bucket may already exist" -ForegroundColor Blue
}

# Deploy to Cloud Run
Write-Host "🚀 Deploying to Cloud Run..." -ForegroundColor Yellow
gcloud run deploy $SERVICE_NAME `
    --image $IMAGE_NAME `
    --platform managed `
    --region $REGION `
    --allow-unauthenticated `
    --memory 2Gi `
    --cpu 2 `
    --timeout 300 `
    --max-instances 10 `
    --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION,GCS_BUCKET_NAME=$BUCKET_NAME,USE_MOCK_STORAGE=false,USE_REAL_AI=true,GOOGLE_AI_API_KEY=AIzaSyDtJcQfikjvgpYYWEYOO777fgtuGn2Oudw,FIREBASE_PROJECT_ID=said-eb2f5,FIREBASE_PROJECT_NUMBER=1026546995867" `
    --service-account firebase-adminsdk-fbsvc@said-eb2f5.iam.gserviceaccount.com

# Get the service URL
$SERVICE_URL = gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)'

Write-Host "✅ Deployment completed!" -ForegroundColor Green
Write-Host "🌐 Service URL: $SERVICE_URL" -ForegroundColor Cyan
Write-Host "📚 API Documentation: $SERVICE_URL/docs" -ForegroundColor Cyan
Write-Host "🔍 ReDoc Documentation: $SERVICE_URL/redoc" -ForegroundColor Cyan

# Test the deployment
Write-Host "🧪 Testing the deployment..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$SERVICE_URL/" -Method Get
    Write-Host "✅ Health check successful!" -ForegroundColor Green
    Write-Host "Response: $($response | ConvertTo-Json)" -ForegroundColor White
} catch {
    Write-Host "⚠️ Health check failed. Service may still be starting up." -ForegroundColor Yellow
    Write-Host "Please check the service URL manually: $SERVICE_URL" -ForegroundColor Yellow
}

Write-Host "`n🎉 Deployment process completed!" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Visit $SERVICE_URL/docs to see the API documentation" -ForegroundColor White
Write-Host "2. Test document upload using the API" -ForegroundColor White
Write-Host "3. Monitor logs: gcloud logs tail 'resource.type=cloud_run_revision'" -ForegroundColor White
