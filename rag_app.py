# Data handling
from models import(
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
    def __init__(self, collection_name):
        self.collection_name = collection_name
        load_dotenv()
        self.groq_client = groq.Client(
            api_key= os.environ.get('GROQ_API_KEY')
        )
        self.client = qdrant_client.QdrantClient(location=":memory:")
        self.qdrant_vector_store = QdrantVectorStore(self.collection_name,self.client,enable_hybrid=True)
        # self.storage_context = StorageContext.from_defaults(vector_store=self.qdrant_vector_store)
        self.vector_index = VectorStoreIndex.from_vector_store(self.qdrant_vector_store)
        self.retriever = self.vector_index.as_retriever(similarity_top_k=3,
                                vector_store_query_mode="hybrid")
        self.datas = []

    async def addToVectorStore(self, url) -> RAGResponse:
        if url not in self.datas:
            try:
                parsedContent = MainContentExtractorReader(
                text_format='markdown').load_data([url])
            except:
                return RAGResponse(errors='parse')

            wikiPipeline = IngestionPipeline(name='Wiki-Pipeline',
                            transformations=[
                                MarkdownNodeParser(),
                                OllamaEmbedding(model_name='mxbai-embed-large')
                            ], vector_store=self.qdrant_vector_store)

            try:
                wikiPipeline.run(show_progress=True, documents=parsedContent)
            except:
                return RAGResponse(errors='ollama')
            
            wikiPipeline.persist(f"./{self.collection_name}_pipeline_cache")
            self.datas.append(url)
            return RAGResponse(message=f"Data of {url} has been added to the vector store.")
        else:
            return RAGResponse(message=f"Data of {url} already exists in vector store.")

    async def loadVectorStore(self, collection_name) -> RAGResponse:
        self.qdrant_vector_store = QdrantVectorStore(collection_name,self.client,enable_hybrid=True)
        self.storage_context = StorageContext.from_defaults(vector_store=self.qdrant_vector_store)
        self.vector_index = VectorStoreIndex.from_vector_store(self.qdrant_vector_store)
        self.collection_name = collection_name
        self.retriever = self.vector_index.as_retriever(similarity_top_k=3,
                                            vector_store_query_mode="hybrid")
        return RAGResponse(message=f'Vector Store {collection_name} has been loaded to memory.')
    
    async def getResponse(self, query, model = 'LLAMA') -> RAGResponse:
        if len(self.datas)>0:
            self.query = query

            try:
                expanded_query = self.groq_client.chat.completions.create(
                messages=[{
                    "role":"system",
                    "content":"You are a helpful assistant who is tasked with creating expanding a single query to\
                        multiple queries, to aid in finding more relevant documents in a vector database using similarity search. "
                },{
                    "role":"user",
                    "content":f"A query will be given to you between the tags and you need to generate 3 optimized queries from it to aid the similarity search.\
                        DONT RETURN ANYTHING ELSE, just return the 3 queries WITHOUT <> separated by a new line.\
                        <QUERY> {self.query} </QUERY>"
                }],
                model='llama3-8b-8192'
                )
            except:
                return RAGResponse(errors='groq')

            expanded_query = expanded_query.choices[0].message.content.split('\n')
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
                        "content":"You will be given some information of a random person, and you will be asked questions regarding that information. YOU ARE THE PERSON in the context and you're being \
                            interviewed by the user. BE THE PERSONALITY in the context and answer the question ONLY on the basis \
                                of the context. If you dont know the answer, just say I dont know. "
                    },
                    {
                        "role":"user",
                        "content":f"Answer the query ONLY on the basis of the context provided. If query is not relevant, \
                            just say you don't know. DONT HALLUCINATE. context and query are given between the tags. return ONLY\
                            the answer to the query.\
                            <CONTEXT> {reranked[0].text}\
                                {reranked[1].text}\
                                {reranked[2].text}\
                            </CONTEXT>
                            <QUERY> {query} </QUERY> "
                    }
                ],
                model= 'mixtral-8x7b-32768' if model =='MIXTRAL' else 'llama3-70b-8192',
                temperature=0.7
                ).choices[0].message.content
            except:
                return RAGResponse(errors='groq') 

            if (expanded_query == '' or response == ''):
                return RAGResponse(message="Groq didn't generate a response.", errors='groq')
            
            return RAGResponse(message=response)
    
        else:
            return RAGResponse(message="No data present in vector store, please add document to vector store.", errors='qdrant')