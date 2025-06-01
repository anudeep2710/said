#!/bin/bash

# Configuration
PROJECT_ID="said-eb2f5"
SERVICE_NAME="talktoyourdocument"
REGION="us-central1"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Deploying TalkToYourDocument to Google Cloud Run"
echo "Project ID: $PROJECT_ID"
echo "Service Name: $SERVICE_NAME"
echo "Region: $REGION"

# Set the project
echo "📋 Setting Google Cloud project..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling required Google Cloud APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable aiplatform.googleapis.com

# Build and push the Docker image
echo "🏗️ Building Docker image..."
gcloud builds submit --tag $IMAGE_NAME

# Create Cloud Storage bucket for documents
BUCKET_NAME="$PROJECT_ID-documents"
echo "📦 Creating Cloud Storage bucket: $BUCKET_NAME"
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$BUCKET_NAME/ || echo "Bucket may already exist"

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --max-instances 10 \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION,GCS_BUCKET_NAME=$BUCKET_NAME,USE_MOCK_STORAGE=false,USE_REAL_AI=true,GOOGLE_AI_API_KEY=AIzaSyDtJcQfikjvgpYYWEYOO777fgtuGn2Oudw,FIREBASE_PROJECT_ID=said-eb2f5,FIREBASE_PROJECT_NUMBER=1026546995867" \
    --service-account firebase-adminsdk-fbsvc@said-eb2f5.iam.gserviceaccount.com

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')

echo "✅ Deployment completed!"
echo "🌐 Service URL: $SERVICE_URL"
echo "📚 API Documentation: $SERVICE_URL/docs"
echo "🔍 ReDoc Documentation: $SERVICE_URL/redoc"

# Test the deployment
echo "🧪 Testing the deployment..."
curl -s "$SERVICE_URL/" | jq '.'
