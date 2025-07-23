from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.background import BackgroundTasks
from pydantic import ConfigDict, BaseModel
from pydantic_ai import Agent
from collections import defaultdict
import base64
import asyncio
import httpx
import json
import io
from datetime import datetime
from typing import AsyncGenerator, Union
from utils.file_utils import save_base64_to_file

from common.logconfig import log

# For text-to-speech - using built-in wave module
import wave

import models.schemas as schemas
from common.ai import model
from core.config import config
from common.agent_details import get_agent_response
from common.a2a import (
    WebhookDetails,
    extract_message_parts,
    extract_webhook_details,
    send_webhook_notification
)


class TextToSpeechAgentOutput(BaseModel):
    audio_base64: str
    duration_seconds: float
    model_config = ConfigDict(arbitrary_types_allowed=True)


text_to_speech_agent = Agent(
    model,
    retries=2,
    output_type=TextToSpeechAgentOutput,
    system_prompt=(
        "You are a text to speech converter. "
        "Given text input, you are to use the available tools to convert it to speech audio"
    ),
)

app = FastAPI()

# Store active tasks in memory (in production, use a database)
active_tasks: dict[str, schemas.Task] = {}


async def convert_text_to_speech_gemini(
    text: str, voice_name: str = "Kore", api_key: str = None
) -> tuple[str, float]:
    """Convert text to speech using Gemini API and return base64 encoded audio with duration."""
    try:
        # Clean and prepare text
        text = text.strip()
        if not text:
            raise ValueError("Empty text provided")

        if not api_key:
            raise ValueError("Gemini API key is required")

        # Prepare the request payload
        payload = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_name}}
                },
            },
        }

        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

        # Make API call to Gemini
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent",
                json=payload,
                headers=headers,
                timeout=60.0,
            )
            response.raise_for_status()

        result = response.json()

        # Extract audio data from response
        if not result.get("candidates") or not result["candidates"][0].get("content"):
            raise ValueError("No audio content in Gemini response")

        audio_data = result["candidates"][0]["content"]["parts"][0]["inlineData"][
            "data"
        ]
        mime_type = result["candidates"][0]["content"]["parts"][0]["inlineData"][
            "mimeType"
        ]

        # The audio is in PCM format (audio/L16;codec=pcm;rate=24000)
        pcm_bytes = base64.b64decode(audio_data)

        # Calculate duration: PCM 16-bit mono at 24kHz
        # Duration = num_samples / sample_rate
        # num_samples = bytes / (sample_width * channels)
        sample_width = 2  # 16-bit = 2 bytes
        channels = 1  # mono
        sample_rate = 24000

        num_samples = len(pcm_bytes) // (sample_width * channels)
        duration_seconds = num_samples / sample_rate

        # Create WAV file in memory
        wav_buffer = io.BytesIO()

        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)  # mono
            wav_file.setsampwidth(sample_width)  # 16-bit
            wav_file.setframerate(sample_rate)  # 24kHz
            wav_file.writeframes(pcm_bytes)

        wav_buffer.seek(0)

        # Encode WAV to base64
        audio_base64 = base64.b64encode(wav_buffer.read()).decode("utf-8")

        return audio_base64, duration_seconds

    except Exception as e:
        raise ValueError(f"Failed to convert text to speech with Gemini: {str(e)}")


async def process_tts_task_background(
    task_id: str,
    text_content: str,
    user_input: str,
    webhook_details: WebhookDetails,
    options: dict,
    api_key: str,
):
    """Background task to process text-to-speech conversion and send webhook."""
    try:
        # Update task status to working
        task = active_tasks[task_id]
        task.status = schemas.TaskStatus(
            state=schemas.TaskState.working, timestamp=datetime.now()
        )

        # Send working status via webhook
        await send_webhook_notification(webhook_details, task)

        response_parts = []
        artifacts = []

        try:
            # Convert text to speech
            audio_base64, duration = await convert_text_to_speech_gemini(
                text_content,
                voice_name=options.get("voice_name", "Kore"),
                api_key=api_key,
            )

            save_base64_to_file(audio_base64, "output/audio/text_to_speech_output.wav")

            # Create artifact with the audio content
            artifact = schemas.Artifact(
                name="text_to_speech_audio",
                description=f"Audio conversion of text ({duration:.1f}s)",
                parts=[
                    schemas.TextPart(text="hehe")
                    # schemas.FilePart(
                    #     file=schemas.FileContent(
                    #         bytes=f"data:audio/wav;base64,{audio_base64}",
                    #         mime_type="audio/wav",
                    #         duration_seconds=duration,
                    #     )
                    # )
                ],
                index=0,
            )
            artifacts.append(artifact)

            # Word count for reference
            word_count = len(text_content.split())

            response_parts.append(
                schemas.TextPart(
                    text=f"✅ Successfully converted {word_count} words to speech audio ({duration:.1f} seconds)"
                )
            )

        except Exception as e:
            response_parts.append(
                schemas.TextPart(text=f"❌ Error processing text-to-speech: {str(e)}")
            )

        # Update task with completion
        completion_message = schemas.Message(
            message_id=uuid4().hex,
            context_id=task.context_id,
            task_id=task_id,
            role="agent",
            parts=response_parts,
        )

        task.status = schemas.TaskStatus(
            state=schemas.TaskState.completed,
            message=completion_message,
            timestamp=datetime.now(),
        )
        task.artifacts = artifacts

        # Send final webhook notification
        await send_webhook_notification(webhook_details, task)

    except Exception as e:
        # Update task with failure
        error_message = schemas.Message(
            message_id=uuid4().hex,
            context_id=task.context_id if task_id in active_tasks else None,
            task_id=task_id,
            role="agent",
            parts=[schemas.TextPart(text=f"❌ Task failed: {str(e)}")],
        )

        if task_id in active_tasks:
            active_tasks[task_id].status = schemas.TaskStatus(
                state=schemas.TaskState.failed,
                message=error_message,
                timestamp=datetime.now(),
            )

            await send_webhook_notification(webhook_details, active_tasks[task_id])


async def stream_tts_processing(
    text_content: str, user_input: str, request_id: str, options: dict, api_key: str
) -> AsyncGenerator[str, None]:
    """Stream text-to-speech processing results as JSON-RPC responses."""
    try:
        # Send processing update
        processing_response = schemas.SendMessageResponse(
            id=request_id,
            result=schemas.Message(
                message_id=uuid4().hex,
                context_id=uuid4().hex,
                role="agent",
                parts=[schemas.TextPart(text=f"Converting text to speech...")],
            ),
        )
        yield f"data: {json.dumps(processing_response.model_dump())}\n\n"

        # Simulate some processing delay
        await asyncio.sleep(0.5)

        # Convert text to speech
        audio_base64, duration = await convert_text_to_speech_gemini(
            text_content, voice_name=options.get("voice_name", "Kore"), api_key=api_key
        )

        # Send the converted audio
        word_count = len(text_content.split())
        success_response = schemas.SendMessageResponse(
            id=request_id,
            result=schemas.Message(
                message_id=uuid4().hex,
                context_id=uuid4().hex,
                role="agent",
                parts=[
                    schemas.TextPart(
                        text=f"✅ Converted {word_count} words to speech audio ({duration:.1f} seconds)"
                    ),
                    schemas.AudioPart(
                        bytes=f"data:audio/wav;base64,{audio_base64}",
                        mime_type="audio/wav",
                        duration_seconds=duration,
                    ),
                ],
            ),
        )
        yield f"data: {json.dumps(success_response.model_dump())}\n\n"

    except Exception as e:
        error_response = schemas.SendMessageResponse(
            id=request_id,
            result=schemas.Message(
                message_id=uuid4().hex,
                context_id=uuid4().hex,
                role="agent",
                parts=[
                    schemas.TextPart(
                        text=f"❌ Error converting text to speech: {str(e)}"
                    )
                ],
            ),
        )
        yield f"data: {json.dumps(error_response.model_dump())}\n\n"


def parse_tts_options(user_input: str) -> dict:
    """Parse TTS options from user input for Gemini voices."""
    options = {"voice_name": "Kore"}  # Default voice

    # Simple parsing for voice selection
    input_lower = user_input.lower()

    # Voice selection - Gemini has various voice options
    if "alloy" in input_lower:
        options["voice_name"] = "Alloy"
    elif "echo" in input_lower:
        options["voice_name"] = "Echo"
    elif "fable" in input_lower:
        options["voice_name"] = "Fable"
    elif "onyx" in input_lower:
        options["voice_name"] = "Onyx"
    elif "nova" in input_lower:
        options["voice_name"] = "Nova"
    elif "shimmer" in input_lower:
        options["voice_name"] = "Shimmer"
    elif "kore" in input_lower:
        options["voice_name"] = "Kore"
    # Add more voice options as available in Gemini
    elif "male" in input_lower or "man" in input_lower:
        options["voice_name"] = "Onyx"  # Default male voice
    elif "female" in input_lower or "woman" in input_lower:
        options["voice_name"] = "Nova"  # Default female voice

    return options


@app.get("/", response_class=HTMLResponse)
def read_tts_agent(request: Request):
    return get_agent_response("text-to-speech", request)


@app.post("/")
async def handle_json_rpc(
    request: Union[
        schemas.SendMessageRequest, schemas.StreamMessageRequest, schemas.GetTaskRequest
    ],
    background_tasks: BackgroundTasks,
):
    if isinstance(request, schemas.GetTaskRequest):
        task_id = request.params.id
        if task_id and task_id in active_tasks:
            return schemas.SendMessageResponse(
                id=uuid4().hex, result=active_tasks[task_id]
            )
        else:
            return schemas.JSONRPCResponse(
                error=schemas.JSONRPCError(code=404, message="Task not found"),
            )

    # Handle message/send and message/stream
    if isinstance(request, (schemas.SendMessageRequest, schemas.StreamMessageRequest)):
        content_parts = extract_message_parts(request, mime_type_filter=["text/plain"])

        user_input = content_parts.joined_text.strip()

        # No text content detected
        if not user_input:
            return schemas.SendMessageResponse(
                id=request.id,
                result=schemas.Message(
                    message_id=uuid4().hex,
                    context_id=uuid4().hex,
                    role="agent",
                    parts=[
                        schemas.TextPart(
                            text="No text content detected. Please provide text to convert to speech."
                        ),
                    ],
                ),
            )

        # Parse TTS options from user input
        tts_options = parse_tts_options(user_input)

        # Get API key from config or environment
        api_key = config.common_model.api_key

        # Extract the actual text content (remove instruction words)
        text_to_convert = user_input
        instruction_words = [
            "convert to speech",
            "text to speech",
            "tts",
            "speak this",
            "read this",
            "make audio",
            "generate speech",
            "alloy",
            "echo",
            "fable",
            "onyx",
            "nova",
            "shimmer",
            "kore",
            "male",
            "female",
            "man",
            "woman",
            "voice",
        ]

        for word in instruction_words:
            text_to_convert = text_to_convert.replace(word, "").strip()

        # Clean up extra spaces
        text_to_convert = " ".join(text_to_convert.split())

        if not text_to_convert:
            text_to_convert = user_input  # Fallback to original input

        # Check for webhook configuration
        webhook_details = extract_webhook_details(request.params)

        # If streaming request or no webhook, stream the response
        if isinstance(request, schemas.StreamMessageRequest) or not webhook_details.url:
            return StreamingResponse(
                stream_tts_processing(
                    text_to_convert, user_input, request.id, tts_options, api_key
                ),
                media_type="text/plain",
            )

        # Webhook present - create task and process in background
        else:
            task_id = uuid4().hex
            context_id = request.params.message.context_id or uuid4().hex

            task = schemas.Task(
                id=task_id,
                context_id=context_id,
                status=schemas.TaskStatus(
                    state=schemas.TaskState.submitted, timestamp=datetime.now()
                ),
                artifacts=[],
                history=[request.params.message],
            )

            # Store task
            active_tasks[task_id] = task

            # Start background processing
            background_tasks.add_task(
                process_tts_task_background,
                task_id,
                text_to_convert,
                user_input,
                webhook_details,
                tts_options,
                api_key,
            )

            # Return task immediately
            return schemas.SendMessageResponse(id=request.id, result=task)

    # Unknown request type
    return schemas.JSONRPCResponse(
        id=getattr(request, "id", None),
        error=schemas.JSONRPCError(code=400, message="Invalid request method"),
    )

@app.get("/.well-known/agent.json")
def agent_card():
    name_suffix = datetime.now() if config.app_env == "local" else ""
    agent_name = f"Text to speech agent {name_suffix}"

    return schemas.AgentCard(
        name=agent_name.strip(),
        description="An agent that converts text to speech audio.",
        url=config.text_to_speech.base_url,
        provider=schemas.AgentProvider(
            organization="Telex",
            url="https://www.telex.im",
        ),
        version="1.0.0",
        documentationUrl=f"{config.text_to_speech.base_url}/docs",
        capabilities=schemas.AgentCapabilities(
            streaming=True,
            pushNotifications=True,
            stateTransitionHistory=True,
        ),
        authentication=schemas.AgentAuthentication(schemes=["Bearer"]),
        defaultInputModes=["text/plain"],
        defaultOutputModes=["audio/wav"],
        skills=[
            schemas.AgentSkill(
                id="convert_text_to_speech",
                name="Convert Text to Speech",
                description="Converts given text to speech audio with customizable options",
                tags=["tts", "speech", "audio", "voice"],
                examples=[
                    "Convert this text to speech",
                    "Make this into audio with Alloy voice",
                    "Generate speech from this text using Nova voice",
                    "Read this text aloud with a male voice",
                    "Use Kore voice to speak this text",
                ],
                inputModes=["text/plain"],
                outputModes=["audio/wav"],
            ),
        ],
    )
