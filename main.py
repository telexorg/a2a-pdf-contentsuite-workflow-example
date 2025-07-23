import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from core.agent_apps import AGENT_APPS
from core.config import config
import apps.request_handler as request_handler_app

app = FastAPI(root_path=config.base_path)

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
def read_main(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "base_path": config.base_path, "agents": AGENT_APPS},
    )


for agent in AGENT_APPS:
    @app.post(f"/{agent.id}")
    async def redirect_to_agent(agent_id: str = agent.id):
        return RedirectResponse(url=f"/{agent_id}/", status_code=307)
    
    app.mount(f"/{agent.id}", agent.app)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/request-handler", app=request_handler_app.app)

if __name__ == "__main__":
    uvicorn.run("main:app", port=config.port, host=config.host, reload=True)
