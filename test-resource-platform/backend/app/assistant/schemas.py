from pydantic import BaseModel, Field


class AssistantMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class AssistantMessageResponse(BaseModel):
    text: str
