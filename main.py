import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from core.agent_apps import AGENT_APPS
from core.config import config
import apps.request_handler as request_handler_app

from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

# only works for router
class ForceSlashRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        scope = request.scope
        path = scope["path"]

        # Only redirect when:
        # - No trailing slash
        # - Path with slash exists in app.routes
        if not path.endswith("/"):
            new_path = path + "/"
            for route in request.app.routes:
                if hasattr(route, "path") and route.path == new_path:
                    # Maintain method & body via 307
                    return RedirectResponse(url=new_path, status_code=307)

        return await call_next(request)

app = FastAPI(root_path=config.base_path)
app.add_middleware(ForceSlashRedirectMiddleware)

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def read_main(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "base_path": config.base_path, "agents": AGENT_APPS},
    )

for agent in AGENT_APPS:
    # agent_base_path = f"{config.base_path}" if config.base_path else ""
    full_prefix = f"/{agent.id}"

    app.mount(full_prefix, agent.app)
    # app.include_router(agent.router, prefix=full_prefix)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/request-handler", app=request_handler_app.app)

if __name__ == "__main__":
    uvicorn.run("main:app", port=config.port, host=config.host, reload=True)
