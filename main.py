from fastapi import FastAPI, BackgroundTasks
from app.scraper import run_scraper

app = FastAPI(title="Facebook Marketplace Scraper")

@app.get("/")
def health():
    return {"status": "ok"}

@app.post("/run")
def run(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scraper)
    return {
        "status": "started",
        "message": "Scraper running in background"
    }
