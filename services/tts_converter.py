import base64
import io
import wave
import httpx

async def convert_text_to_speech_gemini(
    text: str, voice_name: str = "Kore", api_key: str = None
) -> tuple[str, float]:
    if not text.strip():
        raise ValueError("Empty text provided")
    if not api_key:
        raise ValueError("Gemini API key is required")

    payload = {
        "contents": [{"parts": [{"text": text.strip()}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_name}}
            },
        },
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent",
            json=payload,
            headers=headers,
            timeout=60.0,
        )
        response.raise_for_status()

    result = response.json()
    audio_data = result["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
    pcm_bytes = base64.b64decode(audio_data)

    sample_width, channels, sample_rate = 2, 1, 24000
    num_samples = len(pcm_bytes) // (sample_width * channels)
    duration_seconds = num_samples / sample_rate

    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)

    wav_buffer.seek(0)
    audio_base64 = base64.b64encode(wav_buffer.read()).decode("utf-8")
    return audio_base64, duration_seconds
