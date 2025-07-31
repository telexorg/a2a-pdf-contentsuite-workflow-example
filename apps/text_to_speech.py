from pydantic import BaseModel, ConfigDict
from uuid import uuid4
from fastapi import FastAPI, APIRouter, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse
from typing import Union

import models.schemas as schemas
from common.agent_details import get_agent_response
from common.a2a import (
    extract_message_parts,
    extract_webhook_details,
)
from datetime import datetime
from common.ai import model
from pydantic_ai import Agent
from core.config import config

from services.task_handler import process_tts_task_background, stream_tts_processing
from utils.options import parse_tts_options

router = APIRouter()
app = FastAPI()
active_tasks: dict[str, schemas.Task] = {}


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

@app.get("/page.html", response_class=HTMLResponse)
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

    if isinstance(request, (schemas.SendMessageRequest, schemas.StreamMessageRequest)):
        content_parts = extract_message_parts(request, mime_type_filter=["text/plain"])
        user_input = content_parts.joined_text.strip()

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

        tts_options = parse_tts_options(user_input)
        api_key = config.common_model.api_key
        webhook_details = extract_webhook_details(request.params)

        if isinstance(request, schemas.StreamMessageRequest) or not webhook_details.url:
            return StreamingResponse(
                stream_tts_processing(
                    user_input, request.id, tts_options, api_key
                ),
                media_type="text/plain",
            )

        task_id = uuid4().hex
        context_id = request.params.message.context_id or uuid4().hex
        task = schemas.Task(
            id=task_id,
            context_id=context_id,
            status=schemas.TaskStatus(
                state=schemas.TaskState.submitted,
                timestamp=datetime.now(),
            ),
            artifacts=[],
            history=[request.params.message],
        )
        active_tasks[task_id] = task
        background_tasks.add_task(
            process_tts_task_background,
            task_id,
            user_input,
            webhook_details,
            tts_options,
            api_key,
            active_tasks
        )
        return schemas.SendMessageResponse(id=request.id, result=task)

    return schemas.JSONRPCResponse(
        id=getattr(request, "id", None),
        error=schemas.JSONRPCError(code=400, message="Invalid request method"),
    )


@app.get("/.well-known/agent.json")
def agent_card():
    from datetime import datetime
    name_suffix = datetime.now() if config.app_env == "local" else ""
    return schemas.AgentCard(
        name=f"Text to speech agent {name_suffix}".strip(),
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
