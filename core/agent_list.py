from typing import Literal

AGENT_LIST = [
    {
        "id": "pdf-to-markdown",
        "name": "PDF to Markdown",
        "description": "Convert PDFs to Markdown and stream the output.",
        "defaultText": "Convert the attached PDF to markdown",
    },
    {
        "id": "pptx-creator",
        "name": "PPTX Creator",
        "description": "Create beautiful presentations from text.",
        "defaultText": "Create a presentation based on the following content:",
    },
    {
        "id": "mailer",
        "name": "Email Sender",
        "description": "Send rich text emails or files to any recipient.",
        "defaultText": "Send this message to the following email address:",
    },
    {
        "id": "podcast-creator",
        "name": "Podcast Creator",
        "description": "Turn your scripts into audio podcast episodes.",
        "defaultText": "Turn this script into a podcast episode:",
    },
    {
        "id": "spotify-uploader",
        "name": "Spotify Uploader",
        "description": "Publish audio content directly to Spotify.",
        "defaultText": "Upload this audio file to Spotify with the following title and description:",
    },
]

agent_ids = Literal[
    "pdf-to-markdown",
    "pptx-creator",
    "mailer",
    "podcast-creator",
    "spotify-uploader",
]

def get_agent_by_id(id: agent_ids):
    return [agent for agent in AGENT_LIST if agent["id"] == id][0]

