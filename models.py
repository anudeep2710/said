from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

class Language(str, Enum):
    ENGLISH = "en"
    TELUGU = "te"
    HINDI = "hi"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"

class User(BaseModel):
    uid: str
    email: Optional[str] = None
    email_verified: bool = False
    name: Optional[str] = None
    picture: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    language: Language = Language.ENGLISH

class Document(BaseModel):
    document_id: str
    filename: str
    title: str
    text: str
    user_id: Optional[str] = None  # Firebase UID of document owner
    meta: Dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    chat_history: List[ChatMessage] = Field(default_factory=list)
    detected_language: Language = Language.ENGLISH

class QueryRequest(BaseModel):
    document_id: str
    query: str
    query_language: Language = Language.ENGLISH
    target_language: Language = Language.ENGLISH
    include_emotion: bool = False
    chat_history: Optional[List[ChatMessage]] = None

class SummaryRequest(BaseModel):
    document_id: str
    target_language: Language = Language.ENGLISH
    max_length: Optional[int] = None
    include_key_points: bool = True

class EmotionRequest(BaseModel):
    document_id: str
    include_breakdown: bool = True
    target_language: Language = Language.ENGLISH

class EmotionResponse(BaseModel):
    primary_emotion: str
    emotion_breakdown: Dict[str, float]
    reasoning: str
    language: Language

class QueryResponse(BaseModel):
    answer: str
    confidence: float
    emotion: Optional[EmotionResponse] = None
    source_text: Optional[str] = None
    language: Language
    chat_history: List[ChatMessage]

class SummaryResponse(BaseModel):
    summary: str
    key_points: List[str]
    word_count: int
    language: Language