from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Generic message response model."""

    message: str
