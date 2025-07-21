from typing import NamedTuple, Optional
import models.schemas as schemas
import httpx
import base64


class MessageParts(NamedTuple):
    joined_text: str
    text_parts: list[str]
    file_parts: list[schemas.FileContent]
    data_parts: list[dict]


async def extract_message_parts(
    request: schemas.SendMessageRequest,
    mime_type_filter: Optional[list[str]] = None,
    download_files: bool = False,
) -> MessageParts:
    """
    Extracts message parts including optional file download via URI.

    Args:
        request: The incoming SendMessageRequest.
        mime_type_filter: Optional list of MIME types to filter files by.
        download_files: If True, attempts to download file content from URI if not present in `bytes`.

    Returns:
        MessageParts with joined_text, text_parts, file_parts, and data_parts.
    """
    text_parts = [
        part.text for part in request.params.message.parts if part.kind == "text"
    ]

    file_parts_raw = [
        part.file for part in request.params.message.parts if part.kind == "file"
    ]

    data_parts = [
        part.data for part in request.params.message.parts if part.kind == "data"
    ]

    if mime_type_filter:
        file_parts_raw = [f for f in file_parts_raw if f.mime_type in mime_type_filter]

    file_parts: list[schemas.FileContent] = []

    if download_files:
        async with httpx.AsyncClient(timeout=60.0) as client:
            for file_part in file_parts_raw:
                if not file_part.bytes and file_part.uri:
                    try:
                        response = await client.get(file_part.uri)
                        response.raise_for_status()
                        file_part.bytes = base64.b64encode(response.content).decode()
                    except Exception as e:
                        raise ValueError(
                            f"Failed to download file from {file_part.uri}: {str(e)}"
                        )

                file_parts.append(file_part)
    else:
        file_parts = file_parts_raw

    joined_text = "\n".join(text_parts)

    return MessageParts(joined_text, text_parts, file_parts, data_parts)
