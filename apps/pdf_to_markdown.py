from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.background import BackgroundTasks
from markdown_it import MarkdownIt
from pydantic import ConfigDict, BaseModel
from pydantic_ai import Agent
from collections import defaultdict
import base64
import pymupdf
import asyncio
import httpx
import json
from datetime import datetime
from typing import AsyncGenerator, Union

import models.schemas as schemas
from common.ai import model
from core.config import config
from common.agent_details import get_agent_response
from common.a2a import WebhookDetails, extract_message_parts, download_file_content, extract_webhook_details

md = MarkdownIt("commonmark", {"breaks": True, "html": True})


class MarkdownToPDFAgentOutput(BaseModel):
    markdown: str
    model_config = ConfigDict(arbitrary_types_allowed=True)


pdf_to_markdown_agent = Agent(
    model,
    retries=2,
    output_type=MarkdownToPDFAgentOutput,
    system_prompt=(
        "You are a pdf to markdown extractor. "
        "Given a PDF input, you are to use the available tools to convert it to markdown"
    ),
)

app = FastAPI()

# Store active tasks in memory (in production, use a database)
active_tasks: dict[str, schemas.Task] = {}


def decode_base64_file(base64_data: str) -> str:
    """Decode base64 file data to base64 string."""
    try:
        if "," in base64_data:
            base64_data = base64_data.split(",")[1]
        base64.b64decode(base64_data)
        return base64_data
    except Exception as e:
        raise ValueError(f"Failed to decode base64 data: {str(e)}")


def extract_pdf_text(pdf_bytes_b64: str) -> str:
    """Extract text from PDF using base64 encoded bytes."""
    try:
        pdf_bytes = base64.b64decode(pdf_bytes_b64)

        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        text_content = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()
            if text.strip():
                text_content.append(f"## Page {page_num + 1}\n\n{text}")

        doc.close()
        return "\n\n".join(text_content)

    except Exception as e:
        return f"Error extracting text from PDF: {str(e)}"


async def send_webhook_notification(webhook_details: WebhookDetails, task: schemas.Task):
    """Send task update to webhook URL."""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            headers = {"Content-Type": "application/json"}

            if webhook_details.is_telex:
                headers["X-TELEX-API-KEY"] = webhook_details.api_key

            a2a_response = schemas.SendMessageResponse(result=task)

            response = await client.post(
                webhook_details.url,
                json=a2a_response.model_dump(by_alias=True),
                headers=headers,
                timeout=30.0,
            )
            print(response.text)

            response.raise_for_status()
    except Exception as e:
        print(f"Failed to send webhook notification: {e}, {response.text}")



async def process_pdf_task_background(
    task_id: str, unique_pdf_files: list[schemas.FileContent], user_input: str, webhook_details: WebhookDetails
):
    """Background task to process PDF files and send webhook."""
    try:
        # Update task status to working
        task = active_tasks[task_id]
        task.status = schemas.TaskStatus(
            state=schemas.TaskState.working, timestamp=datetime.now()
        )

        response_parts = []
        artifacts = []

        for file_content in unique_pdf_files:
            try:
                # Decode the base64 file content
                base64_string = file_content.bytes if file_content.bytes else await download_file_content(file_content.uri)
                pdf_b64 = decode_base64_file(base64_string)

                # Extract text from PDF
                pdf_text = extract_pdf_text(pdf_b64)

                if pdf_text.startswith("Error"):
                    response_parts.append(schemas.TextPart(text=f"❌ {pdf_text}"))
                    continue

                # Create artifact with the markdown content
                artifact = schemas.Artifact(
                    name=f"{file_content.name}.md",
                    description=f"Markdown conversion of {file_content.name}",
                    parts=[schemas.TextPart(text=pdf_text)],
                    index=len(artifacts),
                )
                artifacts.append(artifact)

                response_parts.append(
                    schemas.TextPart(
                        text=f"✅ Successfully converted {file_content.name} to markdown"
                    )
                )

            except Exception as e:
                response_parts.append(
                    schemas.TextPart(text=f"❌ Error processing {file_content.name}: {str(e)}")
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


async def stream_pdf_processing(
    unique_pdf_files: dict, user_input: str, request_id: str
) -> AsyncGenerator[str, None]:
    """Stream PDF processing results as JSON-RPC responses."""
    for filename, file_content in unique_pdf_files.items():
        try:
            # Send processing update
            processing_response = schemas.SendMessageResponse(
                id=request_id,
                result=schemas.Message(
                    message_id=uuid4().hex,
                    context_id=uuid4().hex,
                    role="agent",
                    parts=[schemas.TextPart(text=f"Processing PDF: **{filename}**")],
                ),
            )
            yield f"data: {json.dumps(processing_response.model_dump())}\n\n"

            # Simulate some processing delay
            await asyncio.sleep(0.1)

            # Decode and process PDF
            pdf_b64 = decode_base64_file(file_content)
            pdf_text = extract_pdf_text(pdf_b64)

            if pdf_text.startswith("Error"):
                error_response = schemas.SendMessageResponse(
                    id=request_id,
                    result=schemas.Message(
                        message_id=uuid4().hex,
                        context_id=uuid4().hex,
                        role="agent",
                        parts=[schemas.TextPart(text=f"❌ {pdf_text}")],
                    ),
                )
                yield f"data: {json.dumps(error_response.model_dump())}\n\n"
            else:
                # Send the converted markdown
                success_response = schemas.SendMessageResponse(
                    id=request_id,
                    result=schemas.Message(
                        message_id=uuid4().hex,
                        context_id=uuid4().hex,
                        role="agent",
                        parts=[schemas.TextPart(text=pdf_text)],
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
                            text=f"❌ Error processing {filename}: {str(e)}"
                        )
                    ],
                ),
            )
            yield f"data: {json.dumps(error_response.model_dump())}\n\n"


@app.get("/", response_class=HTMLResponse)
def read_pdf_to_md(request: Request):
    return get_agent_response("pdf-to-markdown", request)


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
        content_parts = extract_message_parts(
            request, mime_type_filter=["application/pdf", "pdf"]
        )
        
        user_input = content_parts.joined_text

        # No PDF files detected
        if len(content_parts.file_content_list) == 0:
            return schemas.SendMessageResponse(
                id=request.id,
                result=schemas.Message(
                    message_id=uuid4().hex,
                    context_id=uuid4().hex,
                    role="agent",
                    parts=[
                        schemas.TextPart(
                            text="No PDF files detected. Please upload a PDF file to convert to Markdown."
                        ),
                    ],
                ),
            )
        

        webhook_details = extract_webhook_details(request.params)

        # If streaming request or no webhook, stream the response
        if isinstance(request, schemas.StreamMessageRequest) or not webhook_details.url:
            return StreamingResponse(
                stream_pdf_processing(content_parts.file_content_list, user_input, request.id),
                media_type="text/plain",
            )

        # Webhook present - create task and process in background
        else:
            task_id = uuid4().hex
            context_id = request.params.message.context_id or uuid4().hex

            print(f"Handling task {task_id}")

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
                process_pdf_task_background,
                task_id,
                content_parts.file_content_list,
                user_input,
                webhook_details,
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
    agent_name = f"PDF to Markdown agent {name_suffix}"

    return schemas.AgentCard(
        name=agent_name.strip(),
        description="An agent that converts PDF to markdown.",
        url=config.pdf_to_markdown.base_url,
        provider=schemas.AgentProvider(
            organization="Telex",
            url="https://www.telex.im",
        ),
        version="1.0.0",
        documentationUrl=f"{config.pdf_to_markdown.base_url}/docs",
        capabilities=schemas.AgentCapabilities(
            streaming=True,
            pushNotifications=True,
            stateTransitionHistory=True,
        ),
        authentication=schemas.AgentAuthentication(schemes=["Bearer"]),
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        skills=[
            schemas.AgentSkill(
                id="convert_pdf_to_markdown",
                name="Convert PDF to Markdown",
                description="Converts a given PDF to markdown and streams the response",
                tags=["pdf", "markdown"],
                examples=[
                    "Help convert this PDF to markdown",
                    "Extract the new humans section of the pdf and change it to markdown",
                ],
                inputModes=["text/plain"],
                outputModes=["text/plain"],
            ),
        ],
    )
