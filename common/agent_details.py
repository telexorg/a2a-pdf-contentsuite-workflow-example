from fastapi import Request
from fastapi.templating import Jinja2Templates
from core.agent_list import AgentId, get_agent_config_by_id

templates = Jinja2Templates(directory="templates")

def get_agent_response(agent_id: AgentId, request: Request):
    agent_details = get_agent_config_by_id(agent_id)

    return templates.TemplateResponse(
        "agent_home.html",
        {
            "request": request,
            "name": agent_details.name,
            "description": agent_details.description,
            "defaultText": agent_details.default_text
        },
    )