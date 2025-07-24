import os
import time
import json
import asyncio
from datetime import datetime
from uuid import uuid4
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator

from utils.file_utils import save_base64_to_file
from utils.minio import minio_client
from common.a2a import send_webhook_notification
from core.config import config
from common.logconfig import log
import models.schemas as schemas
from .tts_converter import convert_text_to_speech_gemini


async def process_tts_task_background(
    task_id: str,
    user_input: str,
    webhook_details,
    options: dict,
    api_key: str,
    active_tasks: dict,
):
    try:
        task = active_tasks[task_id]
        task.status = schemas.TaskStatus(
            state=schemas.TaskState.working, timestamp=datetime.now()
        )

        audio_base64, duration = await convert_text_to_speech_gemini(
            user_input, options.get("voice_name", "Kore"), api_key
        )

        file_name = f"text_to_speech_output_{uuid4().hex}.wav"
        relative_path = f"output/audio/{file_name}"
        absolute_path = os.path.abspath(relative_path)
        save_base64_to_file(audio_base64, absolute_path)

        try:
            start = time.time()
            minio_client.fput_object(
                config.minio_bucket_name,
                f"{config.minio_bucket_prefix}/{file_name}",
                absolute_path,
            )
            upload_time = round(time.time() - start, 2)
        except Exception as e:
            log.error(str(e))
            upload_time = None

        url = f"https://{config.minio_endpoint}/{config.minio_bucket_name}/{config.minio_bucket_prefix}/{file_name}"
        log.info("converted audio url", url=url, upload_duration=f"{upload_time}s")

        artifact = schemas.Artifact(
            name="text_to_speech_audio",
            description=f"Audio conversion ({duration:.1f}s)",
            parts=[
                schemas.TextPart(text=f"Download: {url}"),
                schemas.FilePart(
                    file=schemas.FileContent(
                        uri=url,
                        mime_type="audio/wav",
                        duration_seconds=duration,
                    )
                ),
            ],
            index=0,
        )

        task.status = schemas.TaskStatus(
            state=schemas.TaskState.completed,
            timestamp=datetime.now(),
            message=schemas.Message(
                message_id=uuid4().hex,
                context_id=task.context_id,
                task_id=task.id,
                role="agent",
                parts=[
                    schemas.TextPart(
                        text=f"✅ Successfully converted text to speech ({duration:.1f}s)"
                    )
                ],
            ),
        )
        task.artifacts = [artifact]
        await send_webhook_notification(webhook_details, task)

    except Exception as e:
        if task_id in active_tasks:
            task = active_tasks[task_id]
            task.status = schemas.TaskStatus(
                state=schemas.TaskState.failed,
                timestamp=datetime.now(),
                message=schemas.Message(
                    message_id=uuid4().hex,
                    context_id=task.context_id,
                    task_id=task_id,
                    role="agent",
                    parts=[schemas.TextPart(text=f"❌ Task failed: {str(e)}")],
                ),
            )
            await send_webhook_notification(webhook_details, task)


async def stream_tts_processing(
    user_input: str, request_id: str, options: dict, api_key: str
) -> AsyncGenerator[str, None]:
    awaitable_sleep = asyncio.sleep(0.5)
    yield f"data: {json.dumps({'id': request_id, 'result': {'parts': [{'text': 'Converting text to speech...'}]}})}\n\n"
    await awaitable_sleep
    try:
        audio_base64, duration = await convert_text_to_speech_gemini(
            user_input, options["voice_name"], api_key
        )
        yield f"data: {json.dumps({'id': request_id, 'result': {'parts': [{'text': f'Success ✅ ({duration:.1f}s)'}, {'audio': {'bytes': f'data:audio/wav;base64,{audio_base64}', 'mime_type': 'audio/wav', 'duration_seconds': duration}}]}})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'id': request_id, 'result': {'parts': [{'text': f'❌ Error: {str(e)}'}]}})}\n\n"
