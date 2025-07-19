import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from core.agent_apps import AGENT_APPS

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def read_main(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "agents": AGENT_APPS})

for agent in AGENT_APPS:
    app.mount(f"/{agent['id']}", agent["app"])

if __name__ == "__main__":
    uvicorn.run("main:app", port=5700, host="127.0.0.1", reload=True)
