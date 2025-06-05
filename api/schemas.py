from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class OrchestrateIn(BaseModel):
    prompt: str = Field(..., description="User prompt/query")
    route: Optional[List[str]] = Field(default=None, description="Optional agent routing preferences")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    flags: List[str] = Field(default_factory=list, description="Conscious-mirror processing flags")
    
class OrchestrateOut(BaseModel):
    response: str = Field(..., description="Generated response")
    agent_type: str = Field(..., description="Agent that handled the request")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    flags_triggered: List[str] = Field(default_factory=list, description="Flags that were triggered")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

class HealthOut(BaseModel):
    status: str = Field(..., description="Health status")
    timestamp: str = Field(..., description="Check timestamp")
    components: Dict[str, bool] = Field(..., description="Component health status")
    version: str = Field(default="3.0.0-alpha", description="API version") 