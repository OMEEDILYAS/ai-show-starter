# generator/tts_openai.py
import os
from openai import OpenAI

OPENAI_TTS_MODEL = os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
OPENAI_TTS_VOICE = os.environ.get("OPENAI_TTS_VOICE", "alloy") #all alloy, verse, aria

def synthesize(text: str, out_path: str) -> None:
    """
    Generate natural speech with OpenAI TTS and write a WAV file to out_path.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=api_key)

    # Response format "wav" so we get raw PCM WAV (easy to mix with ffmpeg)
    resp = client.audio.speech.create(
        model=OPENAI_TTS_MODEL,
        voice=OPENAI_TTS_VOICE,
        input=text,
        response_format="wav",
    )
    # SDK returns bytes-like; write straight to disk
    audio_bytes = resp.read()
    with open(out_path, "wb") as f:
        f.write(audio_bytes)
