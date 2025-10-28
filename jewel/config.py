from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    persona_name: str = Field(default=os.getenv("JEWEL_PERSONA_NAME", "Jewel"))
    user_name: str = Field(default=os.getenv("JEWEL_USER_NAME", "Coco"))
    db_path: str = Field(default=os.getenv("JEWEL_DB_PATH", "./data/jewel.db"))

    openai_api_key: str = Field(default=os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = Field(default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    azure_tts_key: str = Field(default=os.getenv("AZURE_TTS_KEY", ""))
    azure_tts_region: str = Field(default=os.getenv("AZURE_TTS_REGION", ""))
    azure_tts_voice: str = Field(default=os.getenv("AZURE_TTS_VOICE", "en-US-EmmaMultilingualNeural"))

    vosk_model_path: str = Field(default=os.getenv("VOSK_MODEL_PATH", ""))
    telegram_bot_token: str = Field(default=os.getenv("TELEGRAM_BOT_TOKEN", ""))
    # Base URL where the app is hosted (used for absolute links if needed)
    site_url: str = Field(default=os.getenv("SITE_URL", "http://127.0.0.1:8000"))
    # Local secret token to gate sensitive endpoints (set JEWEL_LOCAL_SECRET in .env)
    local_secret_token: str = Field(default=os.getenv("JEWEL_LOCAL_SECRET", ""))

settings = Settings()