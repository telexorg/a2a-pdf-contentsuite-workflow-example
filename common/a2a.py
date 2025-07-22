import httpx
import base64
from typing import NamedTuple, Optional
import models.schemas as schemas


class MessageParts(NamedTuple):
    joined_text: str
    text_parts: list[str]
    file_content_list: list[schemas.FileContent]
    data_parts: list[dict]


class WebhookDetails(NamedTuple):
    url: str
    is_telex: bool
    api_key: str


def extract_message_parts(
    request: schemas.SendMessageRequest, mime_type_filter: Optional[list[str]] = None
) -> MessageParts:
    """
    Reusable function to extract text and file parts from a request.

    Args:
        request: The incoming message request
        mime_type_filter: Optional MIME type to filter files by (e.g., 'application/pdf')

    Returns:
        MessageParts
    """
    text_parts = [
        part.text for part in request.params.message.parts if part.kind == "text"
    ]

    file_content_list = [
        part.file for part in request.params.message.parts if part.kind == "file"
    ]

    data_parts = [
        part.data for part in request.params.message.parts if part.kind == "data"
    ]

    if mime_type_filter:
        file_content_list = [
            part for part in file_content_list if part.mime_type in mime_type_filter
        ]

    joined_text = "\n".join(text_parts)

    return MessageParts(joined_text, text_parts, file_content_list, data_parts)


async def download_file_content(uri: str) -> str:
    """
    Downloads file content from URI and returns it as a base64-encoded string.
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(uri)
            response.raise_for_status()
            return base64.b64encode(response.content).decode()
    except Exception as e:
        raise RuntimeError(f"Failed to download file from {uri}: {str(e)}")


def extract_webhook_details(params: schemas.MessageSendParams) -> WebhookDetails:
    webhook_url = None

    if params.configuration and params.configuration.push_notification_config:
        push_notification_config = params.configuration.push_notification_config
        webhook_url = push_notification_config.url

        if (
            push_notification_config.authentication
            and push_notification_config.authentication.schemes
        ):
            if "TelexApiKey" in push_notification_config.authentication.schemes:
                api_key = push_notification_config.authentication.credentials

    return WebhookDetails(
        url=webhook_url, is_telex=not (not (api_key)), api_key=api_key
    )
