# 🤖 TalkToYourDocument API

> **AI-Powered Document Analysis Platform** - Upload documents and have intelligent conversations with them using Google Gemini AI

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Run-orange.svg)](https://cloud.google.com/run)
[![Firebase](https://img.shields.io/badge/Firebase-Auth-yellow.svg)](https://firebase.google.com)
[![AI](https://img.shields.io/badge/AI-Google%20Gemini-purple.svg)](https://ai.google.dev)

## 🌟 **Live Demo**

🌐 **API Base URL**: https://talktoyourdocument-1026546995867.us-central1.run.app

📚 **Interactive Documentation**: https://talktoyourdocument-1026546995867.us-central1.run.app/docs

## ✨ **Features**

### 🤖 **AI-Powered Analysis**
- **Real AI Integration** - Powered by Google Gemini 1.5 Flash
- **Natural Language Querying** - Ask questions about your documents in plain English
- **Intelligent Summarization** - AI-generated summaries with key points extraction
- **Emotion Analysis** - Advanced sentiment analysis and emotional tone detection
- **Multi-language Support** - 6 languages supported (EN, TE, HI, ES, FR, DE)

### 📄 **Document Processing**
- **Multi-format Support** - PDF, DOCX, TXT file processing
- **Automatic Text Extraction** - Intelligent content extraction from documents
- **Language Detection** - Automatic document language identification
- **Metadata Extraction** - File size, type, and creation information

### 🔐 **Security & Authentication**
- **Firebase Authentication** - Complete user management system
- **JWT Token Verification** - Secure API access with Firebase ID tokens
- **User-specific Data** - Documents associated with authenticated users
- **Role-based Access** - Protected and public endpoints

### ☁️ **Cloud Infrastructure**
- **Google Cloud Run** - Auto-scaling serverless deployment
- **Google Cloud Storage** - Scalable document storage
- **Production Ready** - Comprehensive error handling and logging
- **Auto-scaling** - Handles traffic spikes automatically

## 🚀 **Quick Start**

### **1. Test the Live API**

```bash
# Health check
curl https://talktoyourdocument-1026546995867.us-central1.run.app/

# Upload a document
curl -X POST \
  "https://talktoyourdocument-1026546995867.us-central1.run.app/upload" \
  -F "file=@your_document.pdf"

# Query the document with AI
curl -X POST \
  "https://talktoyourdocument-1026546995867.us-central1.run.app/query" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "your_document_id",
    "query": "What is this document about?",
    "query_language": "en",
    "target_language": "en"
  }'
```

### **2. Local Development**

```bash
# Clone the repository
git clone <repository-url>
cd talktoyourdocument-api

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GOOGLE_AI_API_KEY="your_gemini_api_key"
export USE_MOCK_STORAGE="true"
export USE_REAL_AI="true"

# Run the application
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 📚 **API Endpoints**

### **Core Endpoints**

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/` | Health check | ❌ |
| `GET` | `/docs` | Interactive API documentation | ❌ |
| `POST` | `/upload` | Upload and process document | ⚠️ Optional |
| `GET` | `/documents` | List documents | ⚠️ Optional |
| `POST` | `/query` | AI-powered document querying | ⚠️ Optional |
| `POST` | `/summary` | AI-generated document summary | ⚠️ Optional |
| `POST` | `/emotion` | AI emotion analysis | ⚠️ Optional |
| `DELETE` | `/documents/{id}` | Delete document | ✅ Required |

### **Authentication Endpoints**

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/auth/me` | Get current user info | ✅ Required |

## 🔧 **Configuration**


# Storage Configuration

```

### **Firebase Setup**


## 📊 **Usage Examples**

### **Document Upload**
```json
POST /upload
Content-Type: multipart/form-data

Response:
{
  "document_id": "uuid-here",
  "title": "Document Title",
  "detected_language": "en",
  "user_id": "firebase_uid"
}
```

### **AI Query**
```json
POST /query
{
  "document_id": "uuid-here",
  "query": "What are the main topics?",
  "query_language": "en",
  "target_language": "en"
}

Response:
{
  "answer": "The main topics include...",
  "confidence": 0.9,
  "source_text": "Relevant excerpt..."
}
```

### **AI Summary**
```json
POST /summary
{
  "document_id": "uuid-here",
  "include_key_points": true
}

Response:
{
  "summary": "Document summary...",
  "key_points": ["Point 1", "Point 2"],
  "word_count": 156
}
```

## 📱 **Flutter Integration**

### **Authentication Setup**

```dart
// Add to pubspec.yaml
dependencies:
  firebase_core: ^2.24.2
  firebase_auth: ^4.15.3
  http: ^1.1.0

// Initialize Firebase
await Firebase.initializeApp();

// Sign in user
final user = await FirebaseAuth.instance.signInWithEmailAndPassword(
  email: email,
  password: password,
);

// Get ID token
final idToken = await user.user?.getIdToken();
```

### **API Integration**

```dart
// Make authenticated API calls
final response = await http.post(
  Uri.parse('https://talktoyourdocument-1026546995867.us-central1.run.app/query'),
  headers: {
    'Authorization': 'Bearer $idToken',
    'Content-Type': 'application/json',
  },
  body: jsonEncode({
    'document_id': documentId,
    'query': 'What is this document about?',
  }),
);
```



## 🛠️ **Development**

### **Project Structure**
```
talktoyourdocument-api/
├── main.py                 # FastAPI application
├── models.py              # Pydantic models
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container configuration
├── services/
│   ├── document_service.py      # Document processing
│   ├── llm_service.py          # AI integration
│   ├── storage_service.py      # Cloud storage
│   ├── mock_storage_service.py # Development storage
│   └── firebase_auth_service.py # Authentication
├── auth/
│   └── dependencies.py    # Auth dependencies
└── README.md             # This file
```

### **Key Technologies**
- **Backend**: FastAPI, Python 3.9+
- **AI**: Google Gemini 1.5 Flash API
- **Authentication**: Firebase Auth
- **Storage**: Google Cloud Storage
- **Deployment**: Google Cloud Run
- **Documentation**: OpenAPI/Swagger

## 🏗️ **Architecture**

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Flutter App   │────│  TalkToYourDoc   │────│  Google Gemini  │
│                 │    │      API         │    │      AI         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                       │
         │                        │                       │
    ┌─────────┐              ┌──────────┐           ┌──────────┐
    │Firebase │              │Google    │           │Google    │
    │  Auth   │              │Cloud Run │           │Cloud     │
    └─────────┘              └──────────┘           │Storage   │
                                                    └──────────┘
```

## 📝 **License**

This project is licensed under the MIT License.

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📞 **Support**

- **Documentation**: https://talktoyourdocument-1026546995867.us-central1.run.app/docs
- **Issues**: Create an issue in the repository
- **Email**: Contact the development team

---

**🎉 Built with ❤️ using Google Cloud, Firebase, and AI technologies**