import os
import json
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from typing import List
import shutil

# Get the directory of the current script to build absolute paths
APP_DIR = Path(__file__).parent.resolve()

# The config path can be overridden by an environment variable.
# Defaults to config.json in the same directory as the app.
CONFIG_PATH = os.environ.get("CONFIG_PATH", APP_DIR / "config.json")
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Logic on startup
    print("--- Lifespan startup ---")
    print(f"Current working directory: {os.getcwd()}")
    config_path = Path(CONFIG_PATH)
    example_config_path = APP_DIR / "config.example.json"
    print(f"APP_DIR: {APP_DIR}")
    print(f"Config path: {config_path}")
    print(f"Example config path: {example_config_path}")
    print(f"Config path exists: {config_path.exists()}")
    print(f"Example config path exists: {example_config_path.exists()}")
    if not config_path.exists():
        if example_config_path.exists():
            shutil.copy(example_config_path, config_path)
            print(f"Copied example configuration to {config_path}")
        else:
            print("Example config file not found, cannot create initial config.")

    yield
    # Logic on shutdown
    print("--- Lifespan shutdown ---")


app = FastAPI(
    title="Rclone GUI Hub",
    description="A central hub for managing multiple rclone instances.",
    version="0.1.0",
    lifespan=lifespan
)

class Node(BaseModel):
    name: str
    url: str
    user: str
    # Use an alias because 'pass' is a keyword in Python.
    # The JSON file can still use "pass".
    password: str = Field(..., alias="pass")

class Config(BaseModel):
    nodes: List[Node]
    api_key: str

def load_config() -> Config:
    """Loads the configuration file."""
    try:
        with open(CONFIG_PATH, "r") as f:
            config_data = json.load(f)
            return Config(**config_data)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail=f"Configuration file not found at {CONFIG_PATH}")
    except (json.JSONDecodeError, TypeError) as e:
        raise HTTPException(status_code=500, detail=f"Error parsing configuration file: {e}")

async def get_api_key(api_key_header: str = Depends(api_key_header)):
    """Dependency to verify the API key."""
    config = load_config()
    if not api_key_header or api_key_header != config.api_key:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return api_key_header

@app.get("/")
def read_root():
    return {"message": "Welcome to Rclone GUI Hub"}

@app.get("/api/nodes", dependencies=[Depends(get_api_key)])
def get_nodes():
    """Returns a list of configured rclone nodes (without credentials)."""
    config = load_config()
    return [{"name": node.name, "url": node.url} for node in config.nodes]

# Add more endpoints here to proxy rclone commands, manage jobs, etc.

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
