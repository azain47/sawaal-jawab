from rag_app import RAGapp

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from exceptions import (
    RAGappError,
    OllamaError,
    QdrantError,
    GroqAPIError,
    InvalidDataError,
    ParseError,
    ReRankerError
)
from typing import Callable

from models import(
    Personalities,
    RAGResponse,
    Query,
    Document
)

app = FastAPI(title='Chai Pe Charcha')
ragApp = RAGapp()

def create_exception_handler(
    status_code: int, initial_detail: str
) -> Callable[[Request, RAGappError], JSONResponse]:
    detail = {"message": initial_detail} 

    async def exception_handler(_: Request, exc: RAGappError) -> JSONResponse:
        if exc.message:
            detail["message"] = exc.message

        if exc.name:
            detail["message"] = f"{detail['message']} [{exc.name}]"

        return JSONResponse(
            status_code=status_code, content={"detail": detail["message"]}
        )

    return exception_handler

app.add_exception_handler(
    exc_class_or_status_code=OllamaError,
    handler=create_exception_handler(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        initial_detail="Can't connect to Ollama, please check if ollama is running."
    )
)
app.add_exception_handler(
    exc_class_or_status_code=QdrantError,
    handler=create_exception_handler(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        initial_detail="Can't connect to Qdrant, please check if Qdrant is configured properly."
    )
)
app.add_exception_handler(
    exc_class_or_status_code=ReRankerError,
    handler=create_exception_handler(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        initial_detail="ColBERT Re Ranker is not configured properly. "
    )
)
app.add_exception_handler(
    exc_class_or_status_code=GroqAPIError,
    handler=create_exception_handler(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        initial_detail="Can't connect to Groq."
    )
)
app.add_exception_handler(
    exc_class_or_status_code=InvalidDataError,
    handler=create_exception_handler(
        status.HTTP_406_NOT_ACCEPTABLE,
        initial_detail="Inputs not accepted."
    )
)
app.add_exception_handler(
    exc_class_or_status_code=ParseError,
    handler=create_exception_handler(
        status.HTTP_406_NOT_ACCEPTABLE,
        initial_detail="Error with parsing document."
    )
)

@app.get('/')
def home():
    return {"hi":"mom"}

@app.post("/api/get_response/")
async def get_Response(query: Query) -> RAGResponse:
    if query.query == '':
        raise InvalidDataError(message="No query provided, please provide a query.")
    else:
        groq_response = await ragApp.getResponse(query=query.query, model=query.model)
        if groq_response.errors == 'groq': 
            raise GroqAPIError(message=groq_response.message)
        if groq_response.errors == 'qdrant':
            raise QdrantError(message=groq_response.message) 
        if groq_response.errors == 'rerank':
            raise ReRankerError()
    return RAGResponse(message=groq_response.message)

@app.put('/api/add_person/')
async def add_Personality(data:Document)->RAGResponse:
    if data.url == '':
        raise InvalidDataError(message='No URL provided. Try again.')
    elif data.name == '':
        raise InvalidDataError(message='No name for the person provided. Try again.')
    
    else:
        response = await ragApp.addToVectorStore(data.url, data.name)
        if response.errors=='parse':
            raise ParseError()
        if response.errors=='ollama':
            raise OllamaError()
        return RAGResponse(message = response.message)
    
@app.get('/api/get_persons/')
async def get_personalities()->Personalities:
    return await ragApp.getPersons()

@app.post('/api/load_personality/')
async def load_Personality(data:Document) ->RAGResponse:
    if data.url == '':
        raise InvalidDataError(message='No URL provided. Try again.')
    else:
        response = await ragApp.loadVectorStore(data.url)
        if response.errors == 'qdrant':
            raise QdrantError(message='Personality not found.') 
        return response