# Data handling
from models import(
    Personalities,
    RAGResponse
)

# LLaMa libraries 
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.core import VectorStoreIndex, StorageContext, Settings
from llama_index.postprocessor.colbert_rerank import ColbertRerank
import qdrant_client
from llama_index.core.ingestion import IngestionPipeline

from llama_index.readers.web import MainContentExtractorReader

from llama_index.core.node_parser import MarkdownNodeParser

Settings.embed_model = OllamaEmbedding(model_name='mxbai-embed-large')

# using groq as LLM provider
import groq
from dotenv import load_dotenv
import os

class RAGapp():
    def __init__(self):
        # self.collection_name = collection_name
        load_dotenv()
        self.groq_client = groq.Client(
            api_key= os.environ.get('GROQ_API_KEY')
        )
        self.client = qdrant_client.QdrantClient(location=":memory:")
        self.qdrant_vector_store = None
        # self.storage_context = StorageContext.from_defaults(vector_store=self.qdrant_vector_store)
        self.vector_index = None
        self.retriever = None
        self.datas = {}

    async def addToVectorStore(self, url, name) -> RAGResponse:
        if url not in self.datas.keys():
            prevStore = None
            try:
                parsedContent = MainContentExtractorReader(
                text_format='markdown').load_data([url])
            except:
                return RAGResponse(errors='parse')
            if self.qdrant_vector_store:
                prevStore = self.qdrant_vector_store
            
            self.qdrant_vector_store = QdrantVectorStore(name, self.client, enable_hybrid=True)
             
            wikiPipeline = IngestionPipeline(name='Wiki-Pipeline',
                            transformations=[
                                MarkdownNodeParser(),
                                OllamaEmbedding(model_name='mxbai-embed-large')
                            ], vector_store=self.qdrant_vector_store)

            try:
                wikiPipeline.run(show_progress=True, documents=parsedContent)
            except:
                if prevStore:
                    self.qdrant_vector_store = prevStore
                return RAGResponse(errors='ollama')
            
            # wikiPipeline.persist(f"./{self.collection_name}_pipeline_cache")
            self.datas[url] = [self.qdrant_vector_store, name]

            await self.loadVectorStore(url)

            return RAGResponse(message=f"Data of {url} has been added to the vector store.")
        else:
            await self.loadVectorStore(url)
            return RAGResponse(message=f"Data of {url} already exists in vector store.")

    async def loadVectorStore(self, url) -> RAGResponse:
        try:
            self.qdrant_vector_store = self.datas[url][0]
            self.storage_context = StorageContext.from_defaults(vector_store=self.qdrant_vector_store)
            self.vector_index = VectorStoreIndex.from_vector_store(self.qdrant_vector_store)
            self.retriever = self.vector_index.as_retriever(similarity_top_k=3,
                                                vector_store_query_mode="hybrid")
            return RAGResponse(message=f'Vector Store has been loaded to memory.')
        except:
            return RAGResponse(errors='qdrant')
    
    async def getPersons(self) ->Personalities:
        urls = []
        names = []
        
        for k, v in self.datas.items():
            urls.append(k)
            names.append(v[1])
            
        return Personalities(url=urls,name = names)
    
    async def getResponse(self, query, model = 'LLAMA') -> RAGResponse:
        if len(self.datas)>0:
            self.query = query

            try:
                expanded_query = self.groq_client.chat.completions.create(
                messages=[{
                    "role":"system",
                    "content":'''You are a helpful assistant who is tasked with creating expanding a single query to 
                        multiple queries, to aid in finding more relevant documents in a vector database using similarity search. '''
                },{
                    "role":"user",
                    "content":f'''A query will be given to you between the tags and you need to generate 3 optimized queries from it to aid the similarity search.
                        DONT RETURN ANYTHING ELSE, just return the 3 queries WITHOUT <> separated by a new line.
                        <QUERY> {self.query} </QUERY>'''
                }],
                model= 'mixtral-8x7b-32768' if model =='MIXTRAL' else 'llama3-70b-8192'
                )
            except:
                return RAGResponse(errors='groq')
            
            expanded_query = expanded_query.choices[0].message.content.split('\n')
            
            if (expanded_query == ''):
                return RAGResponse(message="Groq didn't generate a response.", errors='groq')
            
            expanded_query.append(query)
            nodes = []
            
            reranker = ColbertRerank(
                top_n=3, device='cuda'
            )
       
            for q in expanded_query:
                for n in self.retriever.retrieve(q):
                    if n not in nodes:
                        nodes.append(n)
            
            try:
                reranked = reranker.postprocess_nodes(nodes,query_str=query)
            except:
                return RAGResponse(errors='rerank')
            
            try:
                response = self.groq_client.chat.completions.create(
                messages=[
                    {
                        "role":"system",
                        "content":'''ACT LIKE THE PERSONALITY given in the context, match their tone, personality and answer the question on the basis 
                                of the context IN THE WAY THAT PERSON WOULD ANSWER. '''
                    },
                    {
                        "role":"user",
                        "content":f'''Answer the query based of the context provided. ACT LIKE THE PERSON, and if the query is 
                         not relevant, make up an appropriate answer according to the personality. 
                         context and query are given between the tags. return ONLY the answer to the query.
                            <CONTEXT> 
                            {reranked[0].text}
                            {reranked[1].text}
                            {reranked[2].text}
                            </CONTEXT>
                            <QUERY> {query} </QUERY> '''
                    }
                ],
                model= 'mixtral-8x7b-32768' if model =='MIXTRAL' else 'llama3-70b-8192',
                temperature=0.7
                ).choices[0].message.content
            except:
                return RAGResponse(errors='groq') 

            if (response == ''):
                return RAGResponse(message="Groq didn't generate a response.", errors='groq')
            
            return RAGResponse(message=response)
    
        else:
            return RAGResponse(message="No data present in vector store, please add document to vector store.", errors='qdrant')