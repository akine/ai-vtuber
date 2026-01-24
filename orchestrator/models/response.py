from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    vts_connected: bool


class StatsResponse(BaseModel):
    comments_processed: int
    topics_generated: int
    is_speaking: bool
    idle_time: float
