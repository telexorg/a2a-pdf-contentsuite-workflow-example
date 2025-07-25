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
    return get_agent_response("mailer", request)


@app.get("/.well-known/agent.json")
def agent_card():
    return schemas.AgentCard(
        name="Email Sender agent",
        description="An agent that sends emails with optional attachments.",
        url=config.mailer.base_url,
        provider=schemas.AgentProvider(
            organization="Telex",
            url="https://www.telex.im",
        ),
        version="1.0.0",
        documentationUrl=f"{config.mailer.base_url}/docs",
        capabilities=schemas.AgentCapabilities(
            streaming=False,
            pushNotifications=False,
            stateTransitionHistory=True,
        ),
        authentication=schemas.AgentAuthentication(schemes=["Bearer"]),
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        skills=[
            schemas.AgentSkill(
                id="send_email",
                name="Send Email",
                description="Sends an email to the specified recipient",
                tags=["email", "mailer", "send"],
                examples=[
                    "Send a welcome email to John",
                    "Email the report to finance team",
                ],
                inputModes=["text/plain"],
                outputModes=["text/plain"],
            ),
        ],
    )
