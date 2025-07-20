from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from uuid import uuid4
import asyncio
import httpx
import json

import models.schemas as schemas

app = FastAPI()
STREAMS: dict[str, asyncio.Queue] = {}


class FileInput(BaseModel):
    name: str
    mimeType: str
    bytes: str


class SubmitRequest(BaseModel):
    text: Optional[str] = ""
    files: Optional[list[FileInput]] = []
    agent_id: str


class SubmitResponse(BaseModel):
    stream_id: str
    status: str


def format_sse_data(data: dict) -> str:
    """Format data as Server-Sent Events"""
    return f"data: {json.dumps(data)}\n\n"


@app.post("/submit/", response_model=SubmitResponse)
async def submit_message(
    body: SubmitRequest, request: Request, background_tasks: BackgroundTasks
):
    """Submit message and return stream ID for SSE connection"""
    text = body.text or ""
    files = body.files or []
    agent_path = body.agent_id.strip("/")

    if not agent_path:
        # For errors, we still need to create a stream to send the error through SSE
        stream_id = uuid4().hex
        queue = asyncio.Queue()
        STREAMS[stream_id] = queue
        
        # Send error to stream
        background_tasks.add_task(send_error_to_stream, stream_id, {
            "code": -32602,
            "message": "Missing agent_id"
        })
        
        return SubmitResponse(stream_id=stream_id, status="error")

    base_url = str(request.base_url).rstrip("/")
    agent_url_base = f"{base_url}/{agent_path}"
    agent_card_url = f"{agent_url_base}/.well-known/agent.json"

    # Create stream ID immediately
    stream_id = uuid4().hex
    queue = asyncio.Queue()
    STREAMS[stream_id] = queue

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(agent_card_url)
            res.raise_for_status()
            agent_card = schemas.AgentCard(**res.json())
    except Exception as e:
        # Send error to stream
        background_tasks.add_task(send_error_to_stream, stream_id, {
            "code": -32000,
            "message": "Failed to load agent card",
            "data": str(e)
        })
        
        return SubmitResponse(stream_id=stream_id, status="error")

    capabilities = agent_card.capabilities
    agent_url = agent_card.url

    message_id = uuid4().hex

    # Build message parts
    parts: list[schemas.Part] = []
    if text:
        parts.append(schemas.TextPart(text=text))
    for f in files:
        parts.append(
            schemas.FilePart(
                file=schemas.FileContent(
                    name=f.name, mime_type=f.mimeType, bytes=f.bytes
                )
            )
        )

    message = schemas.Message(
        kind="message",
        role="user",
        parts=parts,
        message_id=message_id,
    )

    configuration = schemas.MessageSendConfiguration(
        accepted_output_modes=[
            "text/plain",
            "application/pdf",
            "image/jpeg",
            "image/png",
        ],
        history_length=0,
    )

    # Handle different agent capabilities
    if capabilities.push_notifications:
        # Use webhook
        configuration.push_notification_config = schemas.PushNotificationConfig(
            url=f"{base_url}/webhook/{stream_id}"
        )
        params = schemas.MessageSendParams(message=message, configuration=configuration)

        background_tasks.add_task(
            send_rpc_to_agent_webhook,
            agent_url,
            schemas.SendMessageRequest(params=params),
            stream_id,
        )

    elif capabilities.streaming:
        # Direct streaming
        params = schemas.MessageSendParams(message=message, configuration=configuration)
        background_tasks.add_task(
            forward_stream_to_sse,
            agent_url,
            schemas.StreamMessageRequest(params=params),
            stream_id,
        )

    else:
        # Blocking fallback
        params = schemas.MessageSendParams(message=message, configuration=configuration)
        background_tasks.add_task(
            send_blocking_to_sse,
            agent_url,
            schemas.SendMessageRequest(params=params),
            stream_id,
        )

    return SubmitResponse(stream_id=stream_id, status="processing")


@app.get("/stream/{stream_id}")
async def get_stream(stream_id: str):
    """Get SSE stream for a specific stream ID"""
    if stream_id not in STREAMS:
        # Stream doesn't exist, return error stream
        async def error_stream():
            yield format_sse_data({"error": {"message": "Stream not found"}})
            yield format_sse_data({"final": True})
        
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    queue = STREAMS[stream_id]
    
    async def sse_event_stream():
        try:
            while True:
                item = await queue.get()
                if item == "__done__":
                    yield format_sse_data({"final": True})
                    break
                
                # Parse the item if it's a JSON string
                try:
                    if isinstance(item, str):
                        data = json.loads(item)
                    else:
                        data = item
                    yield format_sse_data(data)
                except json.JSONDecodeError:
                    # If it's not JSON, wrap it in a text field
                    yield format_sse_data({"text": str(item)})
                    
        finally:
            STREAMS.pop(stream_id, None)

    return StreamingResponse(sse_event_stream(), media_type="text/event-stream", 
                           headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@app.post("/webhook/{stream_id}")
async def receive_webhook(stream_id: str, payload: dict):
    """Receive webhook and route to SSE stream"""
    if queue := STREAMS.get(stream_id):
        queue.put_nowait(json.dumps(payload))
        if payload.get("final", False):
            queue.put_nowait("__done__")
    return {"status": "ok"}


async def send_error_to_stream(stream_id: str, error_data: dict):
    """Send error to stream and close it"""
    if queue := STREAMS.get(stream_id):
        queue.put_nowait(json.dumps({"error": error_data}))
        queue.put_nowait("__done__")


async def send_rpc_to_agent_webhook(
    agent_url: str, request_obj: schemas.SendMessageRequest, stream_id: str
):
    """Send RPC request for webhook-based agents"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                agent_url,
                json=request_obj.model_dump(mode="json", exclude_none=True),
                follow_redirects=True,
            )
            res.raise_for_status()
            response = schemas.SendMessageResponse(**res.json())
            
            # If there's an immediate response, send it to the stream
            if hasattr(response, 'result') and response.result:
                if queue := STREAMS.get(stream_id):
                    queue.put_nowait(json.dumps(response.result.model_dump()))
                    
    except Exception as e:
        if queue := STREAMS.get(stream_id):
            queue.put_nowait(json.dumps({"error": {"message": str(e)}}))
            queue.put_nowait("__done__")


async def send_blocking_to_sse(
    agent_url: str, request_obj: schemas.SendMessageRequest, stream_id: str
):
    """Convert blocking response to SSE stream"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                agent_url,
                json=request_obj.model_dump(mode="json", exclude_none=True),
                follow_redirects=True,
            )
            res.raise_for_status()
            response = schemas.SendMessageResponse(**res.json())
            
            if queue := STREAMS.get(stream_id):
                if response.error:
                    queue.put_nowait(json.dumps({"error": response.error.model_dump()}))
                elif response.result:
                    queue.put_nowait(json.dumps(response.result.model_dump()))
                queue.put_nowait("__done__")
                
    except Exception as e:
        if queue := STREAMS.get(stream_id):
            queue.put_nowait(json.dumps({"error": {"message": str(e)}}))
            queue.put_nowait("__done__")


async def forward_stream_to_sse(
    agent_url: str, request_obj: schemas.StreamMessageRequest, stream_id: str
):
    """Forward streaming response to SSE format"""
    async with httpx.AsyncClient(timeout=None) as client:
        try:
            async with client.stream(
                "POST",
                agent_url,
                json=request_obj.model_dump(mode="json", exclude_none=True),
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():  # Skip empty lines
                        if queue := STREAMS.get(stream_id):
                            # Try to parse as JSON, if it fails, send as text
                            try:
                                data = json.loads(line)
                                queue.put_nowait(json.dumps(data))
                            except json.JSONDecodeError:
                                queue.put_nowait(json.dumps({"text": line}))
                                
                if queue := STREAMS.get(stream_id):
                    queue.put_nowait("__done__")
                    
        except Exception as e:
            if queue := STREAMS.get(stream_id):
                queue.put_nowait(json.dumps({"error": {"message": str(e)}}))
                queue.put_nowait("__done__")