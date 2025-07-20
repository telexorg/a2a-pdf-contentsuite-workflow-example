import subprocess
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import models.schemas as schemas
from pydantic import ConfigDict, BaseModel
from pydantic_ai import Agent
from core.config import config

from common.agent_details import get_agent_response
from common.ai import model

app = FastAPI()
templates = Jinja2Templates(directory="templates")


class SlideContent(BaseModel):
    title: str
    content: list[str]
    slide_type: str = "content"

class SlideTitle(BaseModel):
    main: str
    sub: str


class MarkdownToPDFAgentOutput(BaseModel):
    markdown: str
    model_config = ConfigDict(arbitrary_types_allowed=True)


class PresentationStructure(BaseModel):
    title: SlideTitle
    slides: list[SlideContent]


pptx_agent = Agent(
    model,
    retries=2,
    output_type=MarkdownToPDFAgentOutput,
    system_prompt=(
        "You are a pptx creator agent. "
        "Given some text, you convert it into slides format of appropriate length"
        "Then you use available tools to convert the slides into a PPTX"
    ),
)


def create_presentation():
    presentation = PresentationStructure(
        title=SlideTitle(
            main="My awesome presentation",
            sub="python-pptx was here!"
        ),
        slides=[
            SlideContent(
                title="My bro one day",
                content=["One day", "Bro went out", "to do the thing"],
            )
        ],
    )

    ans = subprocess.check_output(["python", "--version"], text=True)
    print(ans)
    ans = subprocess.check_output(["quarto", "render", "slides.qmd"], text=True)
    print(ans)




if __name__ == "__main__":
    create_presentation()


@app.get("/", response_class=HTMLResponse)
def read_pdf_to_md(request: Request):
    return get_agent_response("podcast-creator", request)


@app.get("/.well-known/agent.json")
def agent_card():
    return schemas.AgentCard(
        name="PPTX Creator agent",
        description="An agent that generates PowerPoint presentations.",
        url=config.pptx_creator.base_url,
        provider=schemas.AgentProvider(
            organization="Telex",
            url="https://www.telex.im",
        ),
        version="1.0.0",
        documentationUrl=f"{config.pptx_creator.base_url}/docs",
        capabilities=schemas.AgentCapabilities(
            streaming=False,
            pushNotifications=True,
            stateTransitionHistory=True,
        ),
        authentication=schemas.AgentAuthentication(schemes=["Bearer"]),
        defaultInputModes=["text/plain"],
        defaultOutputModes=[
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ],
        skills=[
            schemas.AgentSkill(
                id="create_pptx",
                name="Create PPTX",
                description="Generates a presentation from plain text input",
                tags=["presentation", "slides", "pptx"],
                examples=[
                    "Create a pitch deck",
                    "Make a 3-slide presentation on climate change",
                ],
                inputModes=["text/plain"],
                outputModes=[
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                ],
            ),
        ],
    )
