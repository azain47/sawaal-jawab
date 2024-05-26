
class RAGappError(Exception):
    def __init__(self, message : str = None , name :str="RAGapp") -> None:
        self.message = message
        self.name = name
        super().__init__(self.message,self.name)

class GroqAPIError(RAGappError):
    pass

class QdrantError(RAGappError):
    pass

class OllamaError(RAGappError):
    pass

class InvalidDataError(RAGappError):
    pass

class ParseError(RAGappError):
    pass

class ReRankerError(RAGappError):
    pass