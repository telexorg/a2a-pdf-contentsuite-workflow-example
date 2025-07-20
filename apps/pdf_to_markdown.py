from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from markdown_it import MarkdownIt
from pydantic import ConfigDict, BaseModel
from pydantic_ai import Agent
from collections import defaultdict
import base64
import pymupdf

import models.schemas as schemas
from common.ai import model
from core.config import config
from common.agent_details import get_agent_response
from common.a2a import extract_message_parts

md = MarkdownIt("commonmark", {"breaks": True, "html": True})


class MarkdownToPDFAgentOutput(BaseModel):
    markdown: str
    model_config = ConfigDict(arbitrary_types_allowed=True)


pdf_to_markdown_agent = Agent(
    model,
    retries=2,
    output_type=MarkdownToPDFAgentOutput,
    system_prompt=(
        "You are a pdf to markdown extractor. "
        "Given a PDF input, you are to use the available tools to convert it to markdown"
    ),
)


app = FastAPI()

def decode_base64_file(base64_data: str) -> str:
    """Decode base64 file data to base64 string."""
    try:
        if "," in base64_data:
            base64_data = base64_data.split(",")[1]
        base64.b64decode(base64_data)
        return base64_data
    except Exception as e:
        raise ValueError(f"Failed to decode base64 data: {str(e)}")


def extract_pdf_text(pdf_bytes_b64: str) -> str:
    """Extract text from PDF using base64 encoded bytes."""
    try:
        pdf_bytes = base64.b64decode(pdf_bytes_b64)

        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        text_content = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()
            if text.strip():
                text_content.append(f"## Page {page_num + 1}\n\n{text}")

        doc.close()
        return "\n\n".join(text_content)

    except Exception as e:
        return f"Error extracting text from PDF: {str(e)}"


@app.get("/", response_class=HTMLResponse)
def read_pdf_to_md(request: Request):
    return get_agent_response("pdf-to-markdown", request)


@app.post("/")
def handle_agent_response(request: schemas.SendMessageRequest):
    content_parts = extract_message_parts(request, mime_type_filter=["application/pdf"])
    unique_pdf_files = defaultdict(str)

    for part in content_parts.file_parts:
        unique_pdf_files[part.name] += part.bytes

    user_input = content_parts.joined_text

    if len(unique_pdf_files.keys()) == 0:
        return schemas.SendMessageResponse(
            result=schemas.Message(
                id=uuid4(),
                contextId=uuid4().hex,
                messageId=uuid4().hex,
                role="agent",
                parts=[
                    schemas.TextPart(
                        text="No PDF files detected. Please upload a PDF file to convert to Markdown."
                    ),
                ],
            )
        )
    
    task_id = uuid4().hex # create a task id since we are sure that we are converting a pdf to markdown

    response_parts = []

    for filename, file_content in unique_pdf_files.items():
        try:
            response_parts.append(
                schemas.TextPart(text=f"Processing PDF: **{filename}**")
            )

            # Decode the base64 file content
            pdf_b64 = decode_base64_file(file_content)

            # Extract text from PDF
            pdf_text = extract_pdf_text(pdf_b64)

            if pdf_text.startswith("Error"):
                response_parts.append(schemas.TextPart(text=f"❌ {pdf_text}"))
                continue

            # For now, just return the extracted text as markdown
            response_parts.append(
                schemas.TextPart(text=pdf_text),
            )

        except Exception as e:
            response_parts.append(
                schemas.TextPart(text=f"❌ Error processing {filename}: {str(e)}")
            )

    return schemas.SendMessageResponse(
        result=schemas.Message(
            id=uuid4(),
            contextId=uuid4().hex,
            messageId=uuid4().hex,
            role="agent",
            parts=response_parts,
        )
    )


@app.get("/.well-known/agent.json")
def agent_card():
    return schemas.AgentCard(
        name=f"PDF to Markdown agent",
        description="An agent that converts PDF to markdown.",
        url=config.pdf_to_markdown.base_url,
        provider=schemas.AgentProvider(
            organization="Telex",
            url="https://www.telex.im",
        ),
        version="1.0.0",
        documentationUrl=f"{config.pdf_to_markdown.base_url}/docs",
        capabilities=schemas.AgentCapabilities(
            streaming=True,
            pushNotifications=True,
            stateTransitionHistory=True,
        ),
        authentication=schemas.AgentAuthentication(schemes=["Bearer"]),
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        skills=[
            schemas.AgentSkill(
                id="convert_pdf_to_markdown",
                name="Convert PDF to Markdown",
                description="Converts a given PDF to markdown and streams the response",
                tags=["pdf", "markdown"],
                examples=[
                    "Help convert this PDF to markdown",
                    "Extract the new humans section of the pdf and change it to markdown",
                ],
                inputModes=["text/plain"],
                outputModes=["text/plain"],
            ),
        ],
    )
