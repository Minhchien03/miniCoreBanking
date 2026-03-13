import logging
from fastapi import FastAPI
import uvicorn
from routes.transfer import router as transfer_router

#Global logger configuration
logging.basicConfig(
    level=logging.INFO, 
    format= "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S")

logger=logging.getLogger(__name__)

app = FastAPI(title="Mini Core Banking API")

app.include_router(transfer_router)
@app.on_event("startup")
async def startup_event():
    logger.info("Starting up...")
    logger.info("Connecting to database...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", reload=True, port=8000)

