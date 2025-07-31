from dataclasses import dataclass
from typing import Literal, Optional
from fastapi import APIRouter
from starlette.types import ASGIApp

AgentId = Literal[
    "pdf-to-markdown",
    "pptx-creator", 
    "mailer",
    "podcast-creator",
    "spotify-uploader",
    "text-to-speech"
]

@dataclass()
class AgentConfig:
    id: AgentId
    name: str
    description: str
    default_text: str
    router: Optional[APIRouter] = None
    app: Optional[ASGIApp] = None

AGENT_CONFIGS: tuple[AgentConfig, ...] = (
    AgentConfig(
        id="pdf-to-markdown",
        name="PDF to Markdown",
        description="Convert PDFs to Markdown and stream the output.",
        default_text="Convert the attached PDF to markdown",
    ),
    AgentConfig(
        id="pptx-creator",
        name="PPTX Creator", 
        description="Create beautiful presentations from text.",
        default_text="Create a presentation based on the following content:",
    ),
    AgentConfig(
        id="mailer",
        name="Email Sender",
        description="Send rich text emails or files to any recipient.",
        default_text="Send this message to the following email address:",
    ),
    AgentConfig(
        id="podcast-creator",
        name="Podcast Creator",
        description="Turn your scripts into audio podcast episodes.",
        default_text="Turn this script into a podcast episode:",
    ),
    AgentConfig(
        id="spotify-uploader", 
        name="Spotify Uploader",
        description="Publish audio content directly to Spotify.",
        default_text="Upload this audio file to Spotify with the following title and description:",
    ),
    AgentConfig(
        id="text-to-speech", 
        name="Text to Speech",
        description="Converts text to speech.",
        default_text="""
        Convert the following convo to speech:

        Authur: Another annoying day to be alive
        Ford: Yeah, but the earth will be destroyed today.
        """,
    ),
)

def get_agent_config_by_id(agent_id: AgentId) -> AgentConfig:
    """Get agent configuration by ID."""
    for config in AGENT_CONFIGS:
        if config.id == agent_id:
            return config
    raise ValueError(f"Agent with ID '{agent_id}' not found")