from typing import NamedTuple, Optional
import models.schemas as schemas

class MessageParts(NamedTuple):
    joined_text: str
    text_parts: list[str]
    file_parts: list[schemas.FileContent]
    data_parts: list[dict]


def extract_message_parts(
    request: schemas.SendMessageRequest, mime_type_filter: Optional[list[str]] = None
) -> MessageParts:
    """
    Reusable function to extract text and file parts from a request.

    Args:
        request: The incoming message request
        mime_type_filter: Optional MIME type to filter files by (e.g., 'application/pdf')

    Returns:
        Tuple of (user_input_text, text_parts_list, file_parts_list)
    """
    text_parts = [
        part.text for part in request.params.message.parts if part.kind == "text"
    ]

    file_parts = [
        part.file
        for part in request.params.message.parts
        if part.kind == "file" and part.file.bytes
    ]

    data_parts = [
        part.data for part in request.params.message.parts if part.kind == "data"
    ]

    if mime_type_filter:
        file_parts = [part for part in file_parts if part.mime_type in mime_type_filter]

    joined_text = "\n".join(text_parts)

    return MessageParts(joined_text, text_parts, file_parts, data_parts)
