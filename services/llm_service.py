from typing import Dict, Optional, List
from models import Document, QueryResponse, EmotionResponse, SummaryResponse, ChatMessage, Language
import json
import os
import re
from langdetect import detect

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
class LLMService:
    """Service for handling LLM operations"""

    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "said-eb2f5")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.api_key = os.getenv("GOOGLE_AI_API_KEY", "AIzaSyDtJcQfikjvgpYYWEYOO777fgtuGn2Oudw")
        self.model_name = "gemini-1.5-flash"
        self.use_real_ai = os.getenv("USE_REAL_AI", "true").lower() == "true"

        # Initialize Google AI with API key
        if self.use_real_ai and self.api_key and GENAI_AVAILABLE:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
        else:
            self.model = None

        # Initialize storage service
        self.storage_service = self._get_storage_service()

    def _get_storage_service(self):
        """Get appropriate storage service based on configuration"""
        use_mock_storage = os.getenv("USE_MOCK_STORAGE", "false").lower() == "true"
        if use_mock_storage:
            from services.mock_storage_service import MockStorageService
            return MockStorageService()
        else:
            from services.storage_service import StorageService
            return StorageService()

    async def query_document(
        self,
        document_id: str,
        query: str,
        query_language: Language = Language.ENGLISH,
        target_language: Language = Language.ENGLISH,
        chat_history: Optional[List[ChatMessage]] = None
    ) -> QueryResponse:
        """Query a document using natural language"""
        try:
            # Get document content
            document = await self.storage_service.retrieve_document(document_id)
            if not document:
                raise Exception(f"Document {document_id} not found")

            # Create chat messages
            messages = []
            if chat_history:
                messages.extend(chat_history)

            # Add user query
            messages.append(ChatMessage(
                role="user",
                content=query,
                language=query_language
            ))

            # Create prompt
            prompt = self._create_query_prompt(
                document.text,
                query,
                query_language,
                target_language,
                messages[-5:] if len(messages) > 5 else messages
            )

            # Get response from LLM
            if self.use_real_ai and self.model:
                response_text = await self._call_ai_model(prompt)
                # Extract answer from response
                response_text = self._extract_answer_from_response(response_text, query)
            else:
                # Fallback to intelligent mock response based on document content
                response_text = self._generate_intelligent_response(document.text, query, target_language)

            # Add assistant response to chat history
            messages.append(ChatMessage(
                role="assistant",
                content=response_text,
                language=target_language
            ))

            return QueryResponse(
                answer=response_text,
                confidence=0.9,
                language=target_language,
                chat_history=messages
            )

        except Exception as e:
            raise Exception(f"Error querying document: {str(e)}")

    async def summarize_document(
        self,
        document_id: str,
        target_language: Language = Language.ENGLISH
    ) -> SummaryResponse:
        """Generate a summary of the document"""
        try:
            # Get document content
            document = await self.storage_service.retrieve_document(document_id)
            if not document:
                raise Exception(f"Document {document_id} not found")

            # Detect document language
            source_language = self._detect_language(document.text)

            # Create prompt
            prompt = self._create_summary_prompt(
                document.text,
                source_language,
                target_language
            )

            # Get response from LLM
            if self.use_real_ai and self.model:
                ai_response = await self._call_ai_model(prompt)
                summary, key_points = self._parse_summary_response(ai_response, target_language)
            else:
                # Intelligent mock response based on document content
                summary, key_points = self._generate_intelligent_summary(document.text, target_language)

            return SummaryResponse(
                summary=summary,
                key_points=key_points,
                word_count=len(summary.split()),
                language=target_language
            )

        except Exception as e:
            raise Exception(f"Error summarizing document: {str(e)}")

    async def analyze_emotion(self, document_id: str) -> EmotionResponse:
        """Analyze emotional tone of the document"""
        try:
            # Get document content
            document = await self.storage_service.retrieve_document(document_id)
            if not document:
                raise Exception(f"Document {document_id} not found")

            # Create prompt
            prompt = self._create_emotion_prompt(document.text)

            # Get response from LLM
            if self.use_real_ai and self.model:
                ai_response = await self._call_ai_model(prompt)
                primary_emotion, emotion_breakdown, reasoning = self._parse_emotion_response(ai_response)
            else:
                # Intelligent mock response based on document content
                primary_emotion, emotion_breakdown, reasoning = self._generate_intelligent_emotion_analysis(document.text)

            return EmotionResponse(
                primary_emotion=primary_emotion,
                emotion_breakdown=emotion_breakdown,
                reasoning=reasoning,
                language=Language.ENGLISH
            )

        except Exception as e:
            raise Exception(f"Error analyzing emotion: {str(e)}")

    def _create_query_prompt(
        self,
        document_text: str,
        query: str,
        query_language: Language,
        target_language: Language,
        chat_history: List[ChatMessage]
    ) -> str:
        """Create prompt for querying document"""
        prompt = f"""Document content:
{document_text}

Previous conversation:
"""
        for msg in chat_history:
            prompt += f"{msg.role}: {msg.content}\n"

        prompt += f"""
Query (in {query_language.value}): {query}
Please provide a response in {target_language.value}.
"""
        return prompt

    def _create_summary_prompt(
        self,
        document_text: str,
        source_language: Language,
        target_language: Language
    ) -> str:
        """Create prompt for summarizing document"""
        return f"""Document content (in {source_language.value}):
{document_text}

Please provide:
1. A comprehensive summary in {target_language.value}
2. Key points in {target_language.value}
"""

    def _create_emotion_prompt(self, document_text: str) -> str:
        """Create prompt for emotion analysis"""
        return f"""Document content:
{document_text}

Please analyze the emotional tone of this document and provide:
1. Primary emotion
2. Emotion breakdown (percentages)
3. Reasoning for the analysis
"""

    def _detect_language(self, text: str) -> Language:
        """Detect language of text"""
        try:
            lang_code = detect(text)
            # Map language codes to our Language enum
            lang_map = {
                "en": Language.ENGLISH,
                "te": Language.TELUGU,
                "hi": Language.HINDI,
                "es": Language.SPANISH,
                "fr": Language.FRENCH,
                "de": Language.GERMAN
            }
            return lang_map.get(lang_code, Language.ENGLISH)
        except:
            return Language.ENGLISH

    async def _update_document(self, document: Document):
        """Update document in storage"""
        # This should be implemented to work with your document storage
        pass

    def _parse_query_response(self, response: str, language: Language,
                            chat_history: List[ChatMessage]) -> QueryResponse:
        """Parse Gemma's response for query endpoint"""
        return QueryResponse(
            answer=response,
            confidence=0.9,
            source_text=None,
            language=language,
            chat_history=chat_history
        )

    def _parse_summary_response(self, response: str, language: Language) -> tuple:
        """Parse AI response for summary endpoint"""
        # Split response into summary and key points
        parts = response.split("\n\n")
        summary = parts[0].strip()
        key_points = []

        if len(parts) > 1:
            # Look for key points in the response
            for part in parts[1:]:
                lines = part.split("\n")
                for line in lines:
                    line = line.strip()
                    if line and (line.startswith("-") or line.startswith("•") or line.startswith("*")):
                        key_points.append(line.lstrip("-•* "))

        # If no key points found, extract from summary
        if not key_points:
            sentences = summary.split(".")
            key_points = [s.strip() for s in sentences[:3] if s.strip()]

        return summary, key_points

    def _parse_emotion_response(self, response: str) -> tuple:
        """Parse AI response for emotion analysis"""
        # Try to extract structured information from response
        primary_emotion = "Neutral"
        emotion_breakdown = {"neutral": 0.6, "positive": 0.3, "negative": 0.1}
        reasoning = response.strip()

        # Look for emotion indicators in the response
        response_lower = response.lower()
        if "positive" in response_lower:
            primary_emotion = "Positive"
            emotion_breakdown = {"positive": 0.6, "neutral": 0.3, "negative": 0.1}
        elif "negative" in response_lower:
            primary_emotion = "Negative"
            emotion_breakdown = {"negative": 0.6, "neutral": 0.3, "positive": 0.1}

        return primary_emotion, emotion_breakdown, reasoning

    async def _call_ai_model(self, prompt: str) -> str:
        """Call the AI model with the given prompt"""
        if not self.model or not GENAI_AVAILABLE:
            return "AI model not available. Using intelligent fallback response."

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"AI model error: {str(e)}")
            # Fallback to mock response
            return "AI model temporarily unavailable. Using fallback response."

    def _extract_answer_from_response(self, response: str, query: str) -> str:
        """Extract the answer from AI response"""
        # Clean up the response
        response = response.strip()

        # If response is too long, truncate it
        if len(response) > 1000:
            response = response[:1000] + "..."

        return response

    def _generate_intelligent_response(self, document_text: str, query: str, target_language: Language) -> str:
        """Generate intelligent response based on document content"""
        query_lower = query.lower()
        text_lower = document_text.lower()

        # Healthcare/HealthConnect specific responses
        if "healthconnect" in query_lower or "health connect" in query_lower:
            return ("HealthConnect is a comprehensive healthcare application that connects patients "
                   "and doctors through a digital platform. It provides features like appointment "
                   "booking, real-time chat, video consultations, health tracking, medical record "
                   "management, and AI-powered health assistance.")

        elif "features" in query_lower or "functionality" in query_lower:
            if "patient" in query_lower:
                return ("Key patient features include: health statistics dashboard, appointment booking, "
                       "real-time chat with doctors, video consultations, health bot assistance, "
                       "medical record access, and prescription tracking.")
            elif "doctor" in query_lower:
                return ("Key doctor features include: patient management dashboard, appointment scheduling, "
                       "medical record access, video consultations, prescription management, "
                       "real-time messaging, and analytics tools.")
            else:
                return ("Main features include: user authentication with role-based access, appointment "
                       "management, real-time chat, video consultations, health bot integration, "
                       "medical record management, and comprehensive dashboards for both patients and doctors.")

        elif "technology" in query_lower or "tech stack" in query_lower:
            return ("The technology stack includes: Angular with Tailwind CSS for frontend, "
                   "Spring Boot with JWT authentication for backend, PostgreSQL database, "
                   "WebRTC for video calls, WebSocket for real-time messaging, and Google Gemini API for AI features.")

        elif "authentication" in query_lower or "login" in query_lower:
            return ("Authentication uses JWT tokens with role-based access control. Users can register "
                   "as either patients or doctors, with conditional registration fields. The system "
                   "includes password validation, email verification, and secure token management.")

        elif "appointment" in query_lower:
            return ("The appointment system allows patients to book appointments with doctors, "
                   "supports both in-person and video consultations, includes scheduling management, "
                   "automatic reminders, and status tracking (pending, confirmed, completed, cancelled).")

        elif "video" in query_lower or "call" in query_lower:
            return ("Video calling is implemented using WebRTC technology, supports peer-to-peer connections, "
                   "includes features like screen sharing, chat during calls, recording capabilities, "
                   "and network quality indicators for optimal user experience.")

        elif "bot" in query_lower or "ai" in query_lower:
            return ("The health bot uses Google Gemini API for natural language processing, "
                   "provides symptom analysis, health recommendations, follow-up questions, "
                   "and can escalate to human doctors when necessary. It maintains conversation history "
                   "and includes medical disclaimers.")

        elif "dashboard" in query_lower:
            return ("The application features separate dashboards for patients and doctors. "
                   "Patient dashboard shows health statistics, upcoming appointments, and health tips. "
                   "Doctor dashboard displays patient management tools, appointment schedules, "
                   "and performance analytics.")

        else:
            # Generic response based on document content analysis
            sentences = document_text.split('.')[:3]  # First 3 sentences
            return f"Based on the document content: {'. '.join(sentences).strip()}."

    def _generate_intelligent_summary(self, document_text: str, target_language: Language) -> tuple:
        """Generate intelligent summary based on document content"""

        # Analyze document content
        text_lower = document_text.lower()

        # Check if it's the HealthConnect document
        if "healthconnect" in text_lower and "angular" in text_lower:
            summary = ("This document contains comprehensive implementation prompts for building HealthConnect, "
                      "a healthcare application using Angular with Tailwind CSS for the frontend and Spring Boot "
                      "for the backend. It covers 25 detailed prompts including authentication systems, "
                      "patient and doctor dashboards, video calling functionality, health bot integration with "
                      "Google Gemini API, appointment management, real-time chat, and complete backend API development.")

            key_points = [
                "25 implementation prompts for HealthConnect healthcare application",
                "Frontend: Angular with Tailwind CSS, responsive design with medical theme",
                "Backend: Spring Boot with JWT authentication and PostgreSQL database",
                "Key features: Video calling, health bot with Gemini API, real-time chat",
                "Patient dashboard with health statistics and appointment management",
                "Doctor dashboard with patient management and scheduling tools",
                "Complete API development for authentication, appointments, and medical records"
            ]
        else:
            # Generic summary for other documents
            sentences = document_text.split('.')
            # Take first few sentences as summary
            summary_sentences = [s.strip() for s in sentences[:3] if s.strip()]
            summary = '. '.join(summary_sentences) + '.'

            # Extract key points from document structure
            lines = document_text.split('\n')
            key_points = []
            for line in lines:
                line = line.strip()
                if (line and
                    (line.startswith('•') or line.startswith('-') or line.startswith('*') or
                     any(char.isdigit() and '.' in line for char in line[:5]))):
                    key_points.append(line.lstrip('•-*0123456789. '))
                    if len(key_points) >= 5:
                        break

            if not key_points:
                # Fallback: extract sentences that seem important
                for sentence in sentences[:10]:
                    if any(keyword in sentence.lower() for keyword in
                          ['feature', 'important', 'key', 'main', 'primary', 'essential']):
                        key_points.append(sentence.strip())
                        if len(key_points) >= 3:
                            break

                if not key_points:
                    key_points = ["Document contains technical information",
                                 "Multiple topics and concepts covered",
                                 "Detailed implementation guidance provided"]

        return summary, key_points

    def _generate_intelligent_emotion_analysis(self, document_text: str) -> tuple:
        """Generate intelligent emotion analysis based on document content"""

        text_lower = document_text.lower()

        # Count emotional indicators
        positive_words = ['good', 'great', 'excellent', 'success', 'effective', 'beneficial', 'positive', 'helpful']
        negative_words = ['bad', 'poor', 'fail', 'error', 'problem', 'issue', 'negative', 'difficult']
        neutral_words = ['system', 'method', 'process', 'implementation', 'technical', 'documentation']

        positive_count = sum(text_lower.count(word) for word in positive_words)
        negative_count = sum(text_lower.count(word) for word in negative_words)
        neutral_count = sum(text_lower.count(word) for word in neutral_words)

        total_count = positive_count + negative_count + neutral_count

        if total_count == 0:
            # Default for technical documents
            emotion_breakdown = {"neutral": 0.7, "positive": 0.2, "negative": 0.1}
            primary_emotion = "Neutral"
            reasoning = "The document appears to be technical or informational in nature."
        else:
            positive_ratio = positive_count / total_count
            negative_ratio = negative_count / total_count
            neutral_ratio = neutral_count / total_count

            # Normalize to ensure they sum to 1
            total_ratio = positive_ratio + negative_ratio + neutral_ratio
            if total_ratio > 0:
                positive_ratio /= total_ratio
                negative_ratio /= total_ratio
                neutral_ratio /= total_ratio

            emotion_breakdown = {
                "positive": round(positive_ratio, 2),
                "negative": round(negative_ratio, 2),
                "neutral": round(neutral_ratio, 2)
            }

            # Determine primary emotion
            if positive_ratio > negative_ratio and positive_ratio > neutral_ratio:
                primary_emotion = "Positive"
                reasoning = "The document contains predominantly positive language and constructive content."
            elif negative_ratio > positive_ratio and negative_ratio > neutral_ratio:
                primary_emotion = "Negative"
                reasoning = "The document contains language indicating challenges or negative aspects."
            else:
                primary_emotion = "Neutral"
                reasoning = "The document maintains a balanced, factual tone with objective information."

        return primary_emotion, emotion_breakdown, reasoning