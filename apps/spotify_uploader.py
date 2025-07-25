from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import models.schemas as schemas
from core.config import config
from common.agent_details import get_agent_response

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/page.html", response_class=HTMLResponse)
def read_pdf_to_md(request: Request):
    return get_agent_response("spotify-uploader", request)

@app.get("/.well-known/agent.json")
def agent_card():
    return schemas.AgentCard(
        name="Spotify Uploader agent",
        description="An agent that uploads audio content to Spotify.",
        url=config.spotify_uploader.base_url,
        provider=schemas.AgentProvider(
            organization="Telex",
            url="https://www.telex.im",
        ),
        version="1.0.0",
        documentationUrl=f"{config.spotify_uploader.base_url}/docs",
        capabilities=schemas.AgentCapabilities(
            streaming=False,
            pushNotifications=True,
            stateTransitionHistory=True,
        ),
        authentication=schemas.AgentAuthentication(schemes=["Bearer"]),
        defaultInputModes=["audio/mpeg"],
        defaultOutputModes=["text/plain"],
        skills=[
            schemas.AgentSkill(
                id="upload_to_spotify",
                name="Upload to Spotify",
                description="Uploads audio files as episodes or tracks to Spotify",
                tags=["spotify", "upload", "music", "podcast"],
                examples=["Upload this podcast to Spotify", "Send this episode to our channel"],
                inputModes=["audio/mpeg"],
                outputModes=["text/plain"],
            ),
        ],
    )
