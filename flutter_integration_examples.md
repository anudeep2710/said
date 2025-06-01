# 🔐 Firebase Authentication Integration with TalkToYourDocument API

## 📱 Flutter Client Implementation

### **1. Firebase Setup in Flutter**

```dart
// pubspec.yaml dependencies
dependencies:
  firebase_core: ^2.24.2
  firebase_auth: ^4.15.3
  http: ^1.1.0
  shared_preferences: ^2.2.2

// main.dart
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_auth/firebase_auth.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp();
  runApp(MyApp());
}
```

### **2. Authentication Service**

```dart
// services/auth_service.dart
import 'package:firebase_auth/firebase_auth.dart';

class AuthService {
  final FirebaseAuth _auth = FirebaseAuth.instance;
  
  // Get current user
  User? get currentUser => _auth.currentUser;
  
  // Get ID token
  Future<String?> getIdToken() async {
    final user = _auth.currentUser;
    if (user != null) {
      return await user.getIdToken();
    }
    return null;
  }
  
  // Sign in with email and password
  Future<UserCredential?> signInWithEmailAndPassword(
    String email, 
    String password
  ) async {
    try {
      return await _auth.signInWithEmailAndPassword(
        email: email,
        password: password,
      );
    } catch (e) {
      print('Sign in error: $e');
      return null;
    }
  }
  
  // Sign up with email and password
  Future<UserCredential?> signUpWithEmailAndPassword(
    String email, 
    String password
  ) async {
    try {
      return await _auth.createUserWithEmailAndPassword(
        email: email,
        password: password,
      );
    } catch (e) {
      print('Sign up error: $e');
      return null;
    }
  }
  
  // Sign out
  Future<void> signOut() async {
    await _auth.signOut();
  }
}
```

### **3. API Service with Authentication**

```dart
// services/api_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'auth_service.dart';

class ApiService {
  static const String baseUrl = 'https://talktoyourdocument-1026546995867.us-central1.run.app';
  final AuthService _authService = AuthService();
  
  // Get headers with authentication
  Future<Map<String, String>> _getHeaders() async {
    final headers = {
      'Content-Type': 'application/json',
    };
    
    final token = await _authService.getIdToken();
    if (token != null) {
      headers['Authorization'] = 'Bearer $token';
    }
    
    return headers;
  }
  
  // Get current user info
  Future<Map<String, dynamic>?> getCurrentUser() async {
    try {
      final headers = await _getHeaders();
      final response = await http.get(
        Uri.parse('$baseUrl/auth/me'),
        headers: headers,
      );
      
      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
      return null;
    } catch (e) {
      print('Get current user error: $e');
      return null;
    }
  }
  
  // Upload document
  Future<Map<String, dynamic>?> uploadDocument(String filePath) async {
    try {
      final token = await _authService.getIdToken();
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl/upload'),
      );
      
      if (token != null) {
        request.headers['Authorization'] = 'Bearer $token';
      }
      
      request.files.add(await http.MultipartFile.fromPath('file', filePath));
      
      final response = await request.send();
      final responseBody = await response.stream.bytesToString();
      
      if (response.statusCode == 200) {
        return json.decode(responseBody);
      }
      return null;
    } catch (e) {
      print('Upload document error: $e');
      return null;
    }
  }
  
  // Query document
  Future<Map<String, dynamic>?> queryDocument({
    required String documentId,
    required String query,
    String queryLanguage = 'en',
    String targetLanguage = 'en',
  }) async {
    try {
      final headers = await _getHeaders();
      final response = await http.post(
        Uri.parse('$baseUrl/query'),
        headers: headers,
        body: json.encode({
          'document_id': documentId,
          'query': query,
          'query_language': queryLanguage,
          'target_language': targetLanguage,
        }),
      );
      
      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
      return null;
    } catch (e) {
      print('Query document error: $e');
      return null;
    }
  }
  
  // Get document summary
  Future<Map<String, dynamic>?> getDocumentSummary({
    required String documentId,
    String targetLanguage = 'en',
    bool includeKeyPoints = true,
  }) async {
    try {
      final headers = await _getHeaders();
      final response = await http.post(
        Uri.parse('$baseUrl/summary'),
        headers: headers,
        body: json.encode({
          'document_id': documentId,
          'target_language': targetLanguage,
          'include_key_points': includeKeyPoints,
        }),
      );
      
      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
      return null;
    } catch (e) {
      print('Get summary error: $e');
      return null;
    }
  }
  
  // Get user's documents
  Future<List<Map<String, dynamic>>?> getUserDocuments() async {
    try {
      final headers = await _getHeaders();
      final response = await http.get(
        Uri.parse('$baseUrl/documents'),
        headers: headers,
      );
      
      if (response.statusCode == 200) {
        final List<dynamic> documents = json.decode(response.body);
        return documents.cast<Map<String, dynamic>>();
      }
      return null;
    } catch (e) {
      print('Get documents error: $e');
      return null;
    }
  }
  
  // Delete document
  Future<bool> deleteDocument(String documentId) async {
    try {
      final headers = await _getHeaders();
      final response = await http.delete(
        Uri.parse('$baseUrl/documents/$documentId'),
        headers: headers,
      );
      
      return response.statusCode == 200;
    } catch (e) {
      print('Delete document error: $e');
      return false;
    }
  }
}
```

### **4. Usage Example in Flutter Widget**

```dart
// screens/document_screen.dart
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/auth_service.dart';

class DocumentScreen extends StatefulWidget {
  @override
  _DocumentScreenState createState() => _DocumentScreenState();
}

class _DocumentScreenState extends State<DocumentScreen> {
  final ApiService _apiService = ApiService();
  final AuthService _authService = AuthService();
  List<Map<String, dynamic>> documents = [];
  bool isLoading = false;
  
  @override
  void initState() {
    super.initState();
    _loadDocuments();
  }
  
  Future<void> _loadDocuments() async {
    setState(() => isLoading = true);
    
    final userDocuments = await _apiService.getUserDocuments();
    if (userDocuments != null) {
      setState(() => documents = userDocuments);
    }
    
    setState(() => isLoading = false);
  }
  
  Future<void> _queryDocument(String documentId, String query) async {
    final result = await _apiService.queryDocument(
      documentId: documentId,
      query: query,
    );
    
    if (result != null) {
      // Show result in dialog or navigate to result screen
      showDialog(
        context: context,
        builder: (context) => AlertDialog(
          title: Text('AI Response'),
          content: Text(result['answer'] ?? 'No response'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: Text('OK'),
            ),
          ],
        ),
      );
    }
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('My Documents'),
        actions: [
          IconButton(
            icon: Icon(Icons.logout),
            onPressed: () async {
              await _authService.signOut();
              Navigator.pushReplacementNamed(context, '/login');
            },
          ),
        ],
      ),
      body: isLoading
          ? Center(child: CircularProgressIndicator())
          : ListView.builder(
              itemCount: documents.length,
              itemBuilder: (context, index) {
                final doc = documents[index];
                return ListTile(
                  title: Text(doc['title'] ?? 'Untitled'),
                  subtitle: Text(doc['filename'] ?? ''),
                  trailing: IconButton(
                    icon: Icon(Icons.chat),
                    onPressed: () => _showQueryDialog(doc['document_id']),
                  ),
                );
              },
            ),
      floatingActionButton: FloatingActionButton(
        onPressed: _uploadDocument,
        child: Icon(Icons.add),
      ),
    );
  }
  
  void _showQueryDialog(String documentId) {
    final controller = TextEditingController();
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Ask a Question'),
        content: TextField(
          controller: controller,
          decoration: InputDecoration(
            hintText: 'What would you like to know?',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              _queryDocument(documentId, controller.text);
            },
            child: Text('Ask'),
          ),
        ],
      ),
    );
  }
  
  Future<void> _uploadDocument() async {
    // Implement file picker and upload logic
    // This would use file_picker package to select files
  }
}
```

## 🔑 **Key Security Features**

✅ **Firebase ID Token Verification** - Backend verifies every request  
✅ **User-Specific Data** - Documents are associated with Firebase UIDs  
✅ **Automatic Token Refresh** - Firebase handles token renewal  
✅ **Secure Headers** - Authorization header with Bearer token  
✅ **Optional Authentication** - Some endpoints work without auth  
✅ **Mock Mode** - Development mode when Firebase isn't configured  

## 🚀 **Ready for Production**

Your TalkToYourDocument API now supports:
- ✅ Firebase Authentication integration
- ✅ User-specific document management
- ✅ Secure API endpoints
- ✅ Flutter client examples
- ✅ Development and production modes
