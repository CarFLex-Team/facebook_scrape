from fastapi import FastAPI, BackgroundTasks
from scraper import run_scraper

app = FastAPI(title="FB Marketplace Scraper API")

@app.get("/")
def root():
    return {"status": "running"}

@app.post("/run")
def run(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scraper)
    return {"status": "started"}