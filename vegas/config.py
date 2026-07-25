"""
Configuration management for the Vegas Assistant.
Loads environment variables and exposes a typed config object.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

@dataclass(frozen=True)
class Config:
    SERVER_NAME: str
    LIVEKIT_URL: Optional[str]
    LIVEKIT_API_KEY: Optional[str]
    LIVEKIT_API_SECRET: Optional[str]
    GROQ_API_KEY: Optional[str]
    SARVAM_API_KEY: Optional[str]
    OPENAI_API_KEY: Optional[str]
    DEEPGRAM_API_KEY: Optional[str]
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str]
    GOOGLE_API_KEY: Optional[str]
    SUPABASE_URL: Optional[str]
    SUPABASE_API_KEY: Optional[str]
    GOOGLE_OAUTH_CREDENTIALS_PATH: Optional[str]
    VEGAS_SANDBOX_ROOT: str

# Instantiate the config object
config = Config(
    SERVER_NAME=os.getenv("SERVER_NAME", "vegas"),
    LIVEKIT_URL=os.getenv("LIVEKIT_URL"),
    LIVEKIT_API_KEY=os.getenv("LIVEKIT_API_KEY"),
    LIVEKIT_API_SECRET=os.getenv("LIVEKIT_API_SECRET"),
    GROQ_API_KEY=os.getenv("GROQ_API_KEY"),
    SARVAM_API_KEY=os.getenv("SARVAM_API_KEY"),
    OPENAI_API_KEY=os.getenv("OPENAI_API_KEY"),
    DEEPGRAM_API_KEY=os.getenv("DEEPGRAM_API_KEY"),
    GOOGLE_APPLICATION_CREDENTIALS=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    GOOGLE_API_KEY=os.getenv("GOOGLE_API_KEY"),
    SUPABASE_URL=os.getenv("SUPABASE_URL"),
    SUPABASE_API_KEY=os.getenv("SUPABASE_API_KEY"),
    GOOGLE_OAUTH_CREDENTIALS_PATH=os.getenv("GOOGLE_OAUTH_CREDENTIALS_PATH"),
    VEGAS_SANDBOX_ROOT=os.getenv("VEGAS_SANDBOX_ROOT", "~/vegas-sandbox"),
)
