from pydantic import BaseModel
from typing import List, Optional
from typing_extensions import Literal

class RAGResponse(BaseModel):
    message: str = None
    errors: str = None

class Personalities(BaseModel):
    url: List[str]
    name: List[str]

class Query(BaseModel):
    query: str
    model: Literal['LLAMA', 'MIXTRAL']

class Document(BaseModel):
    url: str
    name: str