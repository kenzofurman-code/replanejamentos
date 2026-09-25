import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .config import settings
from .database import init_db
from .routers import projects, replan

app = FastAPI(
    title=settings.APP_NAME,
    description="Sistema de Replanejamento Físico-Financeiro pelo Saldo com Ciclos de Medição Flexíveis.",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(projects.router)
app.include_router(replan.router)

# Initialize database tables & warm-up cache
@app.on_event("startup")
def startup_event():
    try:
        init_db()
    except Exception as e:
        print(f"Warning: Database init skipped or failed: {e}")
        
    def _warmup():
        try:
            from .routers.projects import load_project_file
            load_project_file("platea")
            print("Project PLATEA pre-cached in memory successfully.")
        except Exception as err:
            print(f"Pre-caching PLATEA notice: {err}")
            
    import threading
    threading.Thread(target=_warmup, daemon=True).start()

# Mount static files if directory exists
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def read_root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(
            index_path,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return {
        "app": settings.APP_NAME,
        "docs": "/docs",
        "api_projects": "/api/projects",
        "status": "online"
    }

@app.get("/favicon.ico")
def favicon():
    from fastapi import Response
    return Response(status_code=204)

@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}
