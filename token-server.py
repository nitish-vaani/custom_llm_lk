#!/usr/bin/env python3
"""
LiveKit Agent Chat - Unified FastAPI Server
Serves frontend HTML page and provides token generation endpoint.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from livekit import api
import os
import json
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# File paths configuration
FRONTEND_HTML_PATH = "frontend.html"
CONFIG_JSON_PATH = "config.json"

app = FastAPI(
    title="LiveKit Agent Chat Server",
    description="Frontend + Token Server for LiveKit Agent Communication"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentDataSource:
    """
    Abstract data source for agent information.
    Can be switched between config file and database.
    """
    
    def __init__(self, source_type: str = "config"):
        self.source_type = source_type
        
    async def get_agents(self) -> List[Dict[str, Any]]:
        """Get all available agents"""
        if self.source_type == "config":
            return await self._get_agents_from_config()
        elif self.source_type == "database":
            return await self._get_agents_from_database()
        else:
            raise ValueError(f"Unknown source type: {self.source_type}")
    
    async def get_agent_by_id(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get specific agent by ID"""
        agents = await self.get_agents()
        return next((agent for agent in agents if agent.get("id") == agent_id), None)
    
    async def get_app_config(self) -> Dict[str, Any]:
        """Get application configuration"""
        if self.source_type == "config":
            return await self._get_config_from_file()
        elif self.source_type == "database":
            return await self._get_config_from_database()
        else:
            raise ValueError(f"Unknown source type: {self.source_type}")
    
    async def _get_agents_from_config(self) -> List[Dict[str, Any]]:
        """Load agents from config.json file"""
        try:
            config = await self._get_config_from_file()
            return config.get("agents", [])
        except Exception as e:
            logger.error(f"Error loading agents from config: {e}")
            return []
    
    async def _get_config_from_file(self) -> Dict[str, Any]:
        """Load configuration from config.json file"""
        try:
            with open(CONFIG_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file {CONFIG_JSON_PATH} not found")
            raise HTTPException(
                status_code=500, 
                detail=f"Configuration file {CONFIG_JSON_PATH} not found"
            )
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {CONFIG_JSON_PATH}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Invalid JSON in configuration file: {str(e)}"
            )
    
    async def _get_agents_from_database(self) -> List[Dict[str, Any]]:
        """Load agents from database (placeholder for future implementation)"""
        # TODO: Implement database connection and agent retrieval
        # Example structure:
        # async with get_db_connection() as db:
        #     agents = await db.fetch_all("SELECT * FROM agents WHERE active = true")
        #     return [dict(agent) for agent in agents]
        
        logger.warning("Database source not implemented yet, falling back to config")
        return await self._get_agents_from_config()
    
    async def _get_config_from_database(self) -> Dict[str, Any]:
        """Load configuration from database (placeholder for future implementation)"""
        # TODO: Implement database connection and config retrieval
        # Example structure:
        # async with get_db_connection() as db:
        #     config = await db.fetch_one("SELECT * FROM app_config WHERE active = true")
        #     return dict(config) if config else {}
        
        logger.warning("Database config not implemented yet, falling back to file")
        return await self._get_config_from_file()

# Initialize data source (can be switched via environment variable)
DATA_SOURCE_TYPE = os.getenv("AGENT_DATA_SOURCE", "config")  # "config" or "database"
agent_data_source = AgentDataSource(source_type=DATA_SOURCE_TYPE)

class TokenRequest(BaseModel):
    room_name: str
    participant_name: str = "user"
    agent_type: str = "outbound-caller"

@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    """Serve the frontend HTML page with minimal configuration"""
    
    try:
        # Read the frontend.html file
        with open(FRONTEND_HTML_PATH, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        # Set the current server URL for API requests
        base_url = f"{request.url.scheme}://{request.url.netloc}"
        
        # Inject minimal config (just server URL, frontend will fetch agents dynamically)
        minimal_config = {
            "api": {
                "base_url": base_url,
                "agents_endpoint": "/api/agents",
                "config_endpoint": "/api/config",
                "token_endpoint": "/generate_token"
            }
        }
        
        config_json = json.dumps(minimal_config, indent=2)
        
        # Replace placeholder in HTML with minimal config
        html_content = html_content.replace(
            "// CONFIG_PLACEHOLDER", 
            f"const API_CONFIG = {config_json};"
        )
        
        return HTMLResponse(content=html_content)
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, 
            detail=f"Frontend file {FRONTEND_HTML_PATH} not found"
        )
    except Exception as e:
        logger.error(f"Error serving frontend: {e}")
        raise HTTPException(status_code=500, detail=f"Error loading frontend: {str(e)}")

@app.get("/api/agents")
async def get_agents():
    """Get all available agents from configured data source"""
    try:
        agents = await agent_data_source.get_agents()
        return {
            "agents": agents,
            "source": agent_data_source.source_type,
            "total_count": len(agents)
        }
    except Exception as e:
        logger.error(f"Error fetching agents: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching agents: {str(e)}")

@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get specific agent by ID"""
    try:
        agent = await agent_data_source.get_agent_by_id(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching agent: {str(e)}")

@app.get("/api/config")
async def get_config(request: Request):
    """Get application configuration from configured data source"""
    try:
        config = await agent_data_source.get_app_config()
        
        # Add dynamic server information
        base_url = f"{request.url.scheme}://{request.url.netloc}"
        config["server"] = {
            "base_url": base_url,
            "data_source": agent_data_source.source_type
        }
        
        return config
    except Exception as e:
        logger.error(f"Error fetching config: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching configuration: {str(e)}")

@app.post("/generate_token")
async def generate_token(request: TokenRequest):
    """Generate a secure token for frontend to connect to LiveKit room"""
    try:
        # Get LiveKit credentials from environment
        api_key = os.getenv("LIVEKIT_API_KEY")
        api_secret = os.getenv("LIVEKIT_API_SECRET")
        livekit_url = os.getenv("LIVEKIT_URL")
        
        if not api_key or not api_secret:
            raise HTTPException(
                status_code=500, 
                detail="LiveKit credentials not configured"
            )
        
        if not livekit_url:
            raise HTTPException(
                status_code=500,
                detail="LIVEKIT_URL not configured"
            )
        
        logger.info(f"Generating token for room: {request.room_name}, participant: {request.participant_name}")
        
        # Create access token for frontend client
        token = api.AccessToken(api_key, api_secret) \
            .with_identity(request.participant_name) \
            .with_name(request.participant_name) \
            .with_grants(api.VideoGrants(
                room=request.room_name,
                room_join=True,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True
            ))
        
        jwt_token = token.to_jwt()
        
        logger.info(f"Token generated successfully for {request.participant_name}")
        
        return {
            "token": jwt_token,
            "room_name": request.room_name,
            "participant_name": request.participant_name,
            "livekit_url": livekit_url,
            "agent_type": request.agent_type
        }
        
    except Exception as e:
        logger.error(f"Error generating token: {e}")
        raise HTTPException(status_code=500, detail=f"Token generation failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "livekit-agent-chat-server",
        "data_source": agent_data_source.source_type,
        "endpoints": {
            "GET /": "Frontend HTML page",
            "GET /api/agents": "Get all agents",
            "GET /api/agents/{id}": "Get specific agent",
            "GET /api/config": "Get application configuration",
            "POST /generate_token": "Generate LiveKit room token",
            "GET /health": "Health check"
        }
    }

if __name__ == "__main__":
    import uvicorn
    
    # Check required environment variables
    required_vars = ["LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "LIVEKIT_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.error("Please set them in your .env file")
        exit(1)
    
    # Check if required files exist
    if not os.path.exists(FRONTEND_HTML_PATH):
        logger.error(f"Frontend file {FRONTEND_HTML_PATH} not found")
        exit(1)
        
    if DATA_SOURCE_TYPE == "config" and not os.path.exists(CONFIG_JSON_PATH):
        logger.error(f"Configuration file {CONFIG_JSON_PATH} not found")
        exit(1)
    
    logger.info("Starting LiveKit Agent Chat Server...")
    logger.info(f"LiveKit URL: {os.getenv('LIVEKIT_URL')}")
    logger.info(f"Data Source: {DATA_SOURCE_TYPE}")
    logger.info(f"Frontend: http://localhost:8000/")
    logger.info(f"API Docs: http://localhost:8000/docs")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )