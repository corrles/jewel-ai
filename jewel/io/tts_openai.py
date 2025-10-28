"""OpenAI TTS for premium human-like voice.
Uses the OpenAI TTS API (speech endpoint) with configurable voices.
Falls back to Azure TTS if OpenAI key is not set.
"""
import os
import tempfile
from pathlib import Path
from ..config import settings
from openai import OpenAI


def synthesize_openai(text: str, voice: str = "nova", model: str = "tts-1") -> str:
    """Synthesize speech using OpenAI TTS.
    
    Args:
        text: Text to speak
        voice: One of: alloy, echo, fable, onyx, nova, shimmer
        model: tts-1 (faster) or tts-1-hd (higher quality)
    
    Returns:
        Path to the generated audio file (mp3)
    """
    if not settings.openai_api_key:
        raise RuntimeError("OpenAI API key not configured")
    
    client = OpenAI(api_key=settings.openai_api_key)
    
    # Create temp file for output
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp_path = tmp.name
    
    response = client.audio.speech.create(
        model=model,
        voice=voice,
        input=text
    )
    
    # Stream to file
    response.stream_to_file(tmp_path)
    
    return tmp_path


def synthesize(text: str, outfile: str = "./data/out.mp3", voice: str = "nova") -> str:
    """Unified TTS interface. Prefers OpenAI TTS if available, falls back to Azure.
    
    Args:
        text: Text to speak
        outfile: Output file path
        voice: Voice name (OpenAI: alloy/nova/shimmer, Azure: en-US-JennyNeural)
    
    Returns:
        Path to generated audio file
    """
    # Bidirectional mapping between Azure and OpenAI voice identifiers
    azure_to_openai = {
        "en-US-EmmaMultilingualNeural": "nova",
        "en-US-JennyNeural": "shimmer",
        "en-US-AriaNeural": "alloy",
    }
    openai_to_azure = {
        "nova": "en-US-JennyNeural",
        "shimmer": "en-US-JennyNeural",
        "alloy": "en-US-AriaNeural",
        "echo": "en-US-DavisNeural",
        "fable": "en-US-JennyNeural",
        "onyx": "en-US-GuyNeural",
    }
    openai_voice = azure_to_openai.get(voice, voice)

    # Prefer Azure when configured AND the selected voice looks like an Azure voice
    # (e.g., en-US-EmmaMultilingualNeural), or when OpenAI key is missing.
    is_azure_configured = bool(settings.azure_tts_key and settings.azure_tts_region)
    looks_azure_voice = (voice in azure_to_openai) or ("Neural" in voice) or ("-" in voice and voice.count("-") >= 2)
    if is_azure_configured and (looks_azure_voice or not settings.openai_api_key):
        from .tts_azure import synthesize as azure_synthesize
        # Prefer Azure for Azure-typed voices, but fall back to OpenAI if Azure fails
        try:
            return azure_synthesize(text, outfile=outfile, voice=voice)
        except Exception as e:
            # If OpenAI is available, try it as a fallback
            if settings.openai_api_key:
                try:
                    tmp = synthesize_openai(text, voice=azure_to_openai.get(voice, 'nova'))
                    os.makedirs(Path(outfile).parent, exist_ok=True)
                    Path(tmp).rename(outfile)
                    return outfile
                except Exception:
                    # fall through and raise original Azure error
                    pass
            raise RuntimeError(f"Azure TTS failed: {e}")

    # Otherwise use OpenAI first, then fall back to Azure if available
    if not settings.openai_api_key:
        # No OpenAI key at all
        if is_azure_configured:
            from .tts_azure import synthesize as azure_synthesize
            return azure_synthesize(text, outfile=outfile, voice=voice)
        raise RuntimeError("OpenAI TTS failed: OpenAI key missing and Azure not configured")

    try:
        tmp = synthesize_openai(text, voice=openai_voice)
        os.makedirs(Path(outfile).parent, exist_ok=True)
        Path(tmp).rename(outfile)
        return outfile
    except Exception as e:
        if is_azure_configured:
            from .tts_azure import synthesize as azure_synthesize
            # If the selected voice is an OpenAI voice, map to a reasonable Azure default
            azure_voice = voice
            if not looks_azure_voice:
                azure_voice = openai_to_azure.get(voice, settings.azure_tts_voice or "en-US-JennyNeural")
            return azure_synthesize(text, outfile=outfile, voice=azure_voice)
        raise RuntimeError(f"OpenAI TTS failed: {e}")
