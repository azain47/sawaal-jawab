from pydantic import BaseModel

class RAGResponse(BaseModel):
    message: str = None
    errors: str = None

class ChatResponse(BaseModel):
    response: str

class Query(BaseModel):
    query: str

class Document(BaseModel):
    url: str