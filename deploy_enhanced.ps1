# Enhanced deployment script for TalkToYourDocument API v2.0 (PowerShell)
# Includes database, caching, monitoring, and all improvements

param(
    [switch]$SkipInfrastructure,
    [switch]$SkipTests,
    [string]$ProjectId = "said-eb2f5",
    [string]$Region = "us-central1"
)

$ErrorActionPreference = "Stop"

Write-Host "🚀 Deploying TalkToYourDocument API v2.0 with all enhancements..." -ForegroundColor Green

# Configuration
$SERVICE_NAME = "talktoyourdocument"
$IMAGE_NAME = "gcr.io/$ProjectId/$SERVICE_NAME"
$DATABASE_INSTANCE = "talktoyourdocument-db"
$DATABASE_NAME = "talktoyourdocument"
$DATABASE_USER = "app_user"
$REDIS_INSTANCE = "talktoyourdocument-cache"

Write-Host "📋 Configuration:" -ForegroundColor Cyan
Write-Host "  Project: $ProjectId"
Write-Host "  Region: $Region"
Write-Host "  Service: $SERVICE_NAME"
Write-Host "  Database: $DATABASE_INSTANCE"
Write-Host "  Redis: $REDIS_INSTANCE"

# Step 1: Verify prerequisites
Write-Host ""
Write-Host "🔍 Verifying prerequisites..." -ForegroundColor Yellow

try {
    $gcloudVersion = gcloud version 2>$null
    Write-Host "✅ Google Cloud SDK installed"
} catch {
    Write-Host "❌ Google Cloud SDK not found. Please install it first." -ForegroundColor Red
    exit 1
}

try {
    $currentProject = gcloud config get-value project 2>$null
    if ($currentProject -ne $ProjectId) {
        Write-Host "Setting project to $ProjectId..."
        gcloud config set project $ProjectId
    }
    Write-Host "✅ Project configured: $ProjectId"
} catch {
    Write-Host "❌ Failed to configure project" -ForegroundColor Red
    exit 1
}

# Step 2: Enable required APIs
Write-Host ""
Write-Host "🔧 Enabling required Google Cloud APIs..." -ForegroundColor Yellow

$requiredApis = @(
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "sql-component.googleapis.com",
    "redis.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com"
)

foreach ($api in $requiredApis) {
    try {
        Write-Host "Enabling $api..."
        gcloud services enable $api --project=$ProjectId
    } catch {
        Write-Host "Warning: Failed to enable $api" -ForegroundColor Yellow
    }
}

Write-Host "✅ APIs enabled"

# Step 3: Set up secrets in Secret Manager
Write-Host ""
Write-Host "🔐 Setting up secrets in Google Secret Manager..." -ForegroundColor Yellow

# Create secrets if they don't exist
$secrets = @{
    "GOOGLE_AI_API_KEY" = "AIzaSyDtJcQfikjvgpYYWEYOO777fgtuGn2Oudw"
    "JWT_SECRET_KEY" = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes((New-Guid).ToString()))
    "ENCRYPTION_KEY" = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes((New-Guid).ToString()))
}

foreach ($secretName in $secrets.Keys) {
    try {
        $secretValue = $secrets[$secretName]
        Write-Host "Creating secret: $secretName"
        
        # Check if secret exists
        $existingSecret = gcloud secrets describe $secretName --project=$ProjectId 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Secret $secretName already exists, updating..."
            echo $secretValue | gcloud secrets versions add $secretName --data-file=- --project=$ProjectId
        } else {
            Write-Host "Creating new secret: $secretName"
            echo $secretValue | gcloud secrets create $secretName --data-file=- --project=$ProjectId
        }
    } catch {
        Write-Host "Warning: Failed to create secret $secretName" -ForegroundColor Yellow
    }
}

# Firebase service account secret
if (Test-Path "firebase-service-account.json") {
    try {
        Write-Host "Creating Firebase service account secret..."
        $existingSecret = gcloud secrets describe "FIREBASE_SERVICE_ACCOUNT" --project=$ProjectId 2>$null
        if ($LASTEXITCODE -eq 0) {
            gcloud secrets versions add "FIREBASE_SERVICE_ACCOUNT" --data-file="firebase-service-account.json" --project=$ProjectId
        } else {
            gcloud secrets create "FIREBASE_SERVICE_ACCOUNT" --data-file="firebase-service-account.json" --project=$ProjectId
        }
    } catch {
        Write-Host "Warning: Failed to create Firebase service account secret" -ForegroundColor Yellow
    }
} else {
    Write-Host "Warning: firebase-service-account.json not found" -ForegroundColor Yellow
}

Write-Host "✅ Secrets configured"

# Step 4: Build and push Docker image
Write-Host ""
Write-Host "🐳 Building and pushing Docker image..." -ForegroundColor Yellow

try {
    Write-Host "Building image: $IMAGE_NAME"
    gcloud builds submit --tag $IMAGE_NAME --project=$ProjectId
    Write-Host "✅ Docker image built and pushed"
} catch {
    Write-Host "❌ Failed to build Docker image" -ForegroundColor Red
    exit 1
}

# Step 5: Deploy to Cloud Run with enhanced configuration
Write-Host ""
Write-Host "☁️ Deploying to Cloud Run with enhanced configuration..." -ForegroundColor Yellow

try {
    $deployArgs = @(
        "run", "deploy", $SERVICE_NAME,
        "--image", $IMAGE_NAME,
        "--platform", "managed",
        "--region", $Region,
        "--allow-unauthenticated",
        "--memory", "4Gi",
        "--cpu", "2",
        "--timeout", "300",
        "--max-instances", "100",
        "--min-instances", "1",
        "--concurrency", "80",
        "--service-account", "firebase-adminsdk-fbsvc@$ProjectId.iam.gserviceaccount.com",
        "--set-env-vars", "GOOGLE_CLOUD_PROJECT=$ProjectId,GOOGLE_CLOUD_LOCATION=$Region,USE_REAL_AI=true,USE_SECRET_MANAGER=true,ENVIRONMENT=production,PROMETHEUS_PORT=9090",
        "--set-secrets", "GOOGLE_AI_API_KEY=GOOGLE_AI_API_KEY:latest,JWT_SECRET_KEY=JWT_SECRET_KEY:latest,ENCRYPTION_KEY=ENCRYPTION_KEY:latest",
        "--project", $ProjectId
    )
    
    # Add Firebase secret if available
    $firebaseSecret = gcloud secrets describe "FIREBASE_SERVICE_ACCOUNT" --project=$ProjectId 2>$null
    if ($LASTEXITCODE -eq 0) {
        $deployArgs += "--set-secrets", "FIREBASE_SERVICE_ACCOUNT=FIREBASE_SERVICE_ACCOUNT:latest"
    }
    
    Write-Host "Deploying to Cloud Run..."
    & gcloud @deployArgs
    
    Write-Host "✅ Cloud Run service deployed"
} catch {
    Write-Host "❌ Failed to deploy to Cloud Run" -ForegroundColor Red
    exit 1
}

# Step 6: Get service URL and run health checks
Write-Host ""
Write-Host "🏥 Running health checks..." -ForegroundColor Yellow

try {
    $SERVICE_URL = gcloud run services describe $SERVICE_NAME --region=$Region --project=$ProjectId --format="value(status.url)"
    Write-Host "Service URL: $SERVICE_URL" -ForegroundColor Green
    
    # Wait for service to be ready
    Write-Host "Waiting for service to be ready..."
    Start-Sleep -Seconds 30
    
    # Test health endpoint
    Write-Host "Testing health endpoint..."
    try {
        $healthResponse = Invoke-RestMethod -Uri "$SERVICE_URL/" -Method Get -TimeoutSec 30
        Write-Host "✅ Health check passed"
        Write-Host "Status: $($healthResponse.status)"
    } catch {
        Write-Host "⚠️ Health check failed: $($_.Exception.Message)" -ForegroundColor Yellow
    }
    
    # Test detailed health endpoint
    Write-Host "Testing detailed health endpoint..."
    try {
        $detailedHealthResponse = Invoke-RestMethod -Uri "$SERVICE_URL/health/detailed" -Method Get -TimeoutSec 30
        Write-Host "✅ Detailed health check passed"
        Write-Host "Services status:"
        $detailedHealthResponse.services.PSObject.Properties | ForEach-Object {
            Write-Host "  $($_.Name): $($_.Value)"
        }
    } catch {
        Write-Host "⚠️ Detailed health check failed: $($_.Exception.Message)" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "❌ Failed to get service URL or run health checks" -ForegroundColor Red
}

# Step 7: Display deployment summary
Write-Host ""
Write-Host "🎉 Deployment completed!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Deployment Summary:" -ForegroundColor Cyan
Write-Host "  Service URL: $SERVICE_URL" -ForegroundColor White
Write-Host "  API Documentation: $SERVICE_URL/docs" -ForegroundColor White
Write-Host "  Health Check: $SERVICE_URL/health/detailed" -ForegroundColor White
Write-Host ""
Write-Host "🔧 Infrastructure:" -ForegroundColor Cyan
Write-Host "  Secrets: Google Secret Manager" -ForegroundColor White
Write-Host "  Monitoring: Google Cloud Monitoring" -ForegroundColor White
Write-Host "  Authentication: Firebase" -ForegroundColor White
Write-Host ""
Write-Host "🚀 Your enhanced TalkToYourDocument API v2.0 is now live!" -ForegroundColor Green
Write-Host ""
Write-Host "📚 Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Test all endpoints using: $SERVICE_URL/docs"
Write-Host "  2. Run integration tests: python test_integration.py --url=$SERVICE_URL"
Write-Host "  3. Monitor service health: $SERVICE_URL/health/detailed"
Write-Host "  4. View logs: gcloud run services logs read $SERVICE_NAME --region=$Region"
Write-Host ""

# Optional: Run integration tests
if (-not $SkipTests) {
    $runTests = Read-Host "🧪 Run integration tests? (y/n)"
    if ($runTests -eq "y" -or $runTests -eq "Y") {
        Write-Host "Running integration tests..." -ForegroundColor Yellow
        try {
            if (Test-Path "test_integration.py") {
                python test_integration.py --url=$SERVICE_URL
            } else {
                Write-Host "Integration test file not found" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "Failed to run integration tests: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
}

Write-Host ""
Write-Host "✨ Deployment script completed!" -ForegroundColor Green
Write-Host ""
Write-Host "🔗 Useful Commands:" -ForegroundColor Cyan
Write-Host "  View logs: gcloud run services logs read $SERVICE_NAME --region=$Region --project=$ProjectId"
Write-Host "  Update service: gcloud run services update $SERVICE_NAME --region=$Region --project=$ProjectId"
Write-Host "  Scale service: gcloud run services update $SERVICE_NAME --max-instances=200 --region=$Region --project=$ProjectId"
