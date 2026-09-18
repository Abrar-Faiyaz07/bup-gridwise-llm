import sys
import os

# Add gridwise-api directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
gridwise_api_dir = os.path.join(root_dir, "gridwise-api")

if gridwise_api_dir not in sys.path:
    sys.path.insert(0, gridwise_api_dir)

from app.main import app

@app.get("/")
async def root():
    return {
        "message": "GridWise LLM Microgrid Energy Optimizer API is running",
        "status": "online",
        "health": "/health",
        "docs": "/docs"
    }
