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


def register_agent_routes(agent):
    prefix = f"/{agent.id}"

    @app.get(prefix)
    async def redirect_to_slash():
        return RedirectResponse(url=f"{prefix}/", status_code=307)

    @app.post(prefix)
    async def redirect_post_to_slash():
        return RedirectResponse(url=f"{prefix}/", status_code=307)

    app.mount(f"{prefix}/", agent.app)

for agent in AGENT_APPS:
    register_agent_routes(agent)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/request-handler", app=request_handler_app.app)

if __name__ == "__main__":
    uvicorn.run("main:app", port=config.port, host=config.host, reload=True)
