from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import schemas
from core.config import config
from common.agent_details import get_agent_response

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def read_pdf_to_md(request: Request):
    return get_agent_response("podcast-creator", request)

@app.get("/.well-known/agent.json")
def agent_card():
    return schemas.AgentCard(
        name="Podcast Creator agent",
        description="An agent that creates podcast episodes from text or scripts.",
        url=config.podcast_creator.base_url,
        provider=schemas.AgentProvider(
            organization="Telex",
            url="https://www.telex.im",
        ),
        version="1.0.0",
        documentationUrl=f"{config.podcast_creator.base_url}/docs",
        capabilities=schemas.AgentCapabilities(
            streaming=False,
            pushNotifications=True,
            stateTransitionHistory=True,
        ),
        authentication=schemas.AgentAuthentication(schemes=["Bearer"]),
        defaultInputModes=["text/plain"],
        defaultOutputModes=["audio/mpeg"],
        skills=[
            schemas.AgentSkill(
                id="create_podcast",
                name="Create Podcast",
                description="Generates an audio podcast from a script",
                tags=["podcast", "audio"],
                examples=["Make a podcast on AI ethics", "Turn this script into an episode"],
                inputModes=["text/plain"],
                outputModes=["audio/mpeg"],
            ),
        ],
    )
