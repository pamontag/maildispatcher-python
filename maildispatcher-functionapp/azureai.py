from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, OpenAIChatPromptExecutionSettings, AzureTextEmbedding
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase
from semantic_kernel.contents import ChatHistory 
from semantic_kernel.memory.semantic_text_memory import SemanticTextMemory
from semantic_kernel.connectors.memory.azure_cosmosdb_no_sql import AzureCosmosDBNoSQLMemoryStore
from azure.cosmos.aio import CosmosClient

import prompts
import time
import os
import logging
import tiktoken
 

class AzureAI:
    def __init__(self):
        self.COSMOS_CONNECTION_STRING = os.getenv("COSMOS_CONNECTION_STRING")
        self.COSMOS_DATABASE = os.getenv("COSMOS_DATABASE_NAME")
        self.COSMOS_COLLECTION = os.getenv("COSMOS_COLLECTION_NAME")    
        self.chat_completion_service = AzureChatCompletion()
        self.embedding_service = AzureTextEmbedding(service_id="text_embedding")   

        # Initialize the kernel
        self.kernel = Kernel()

        # Add the chat completion service created above to the kernel
        self.kernel.add_service(self.chat_completion_service)
        self.kernel.add_service(self.embedding_service)

        # Retrieve the chat completion service by type
        self.chat_completion_service = self.kernel.get_service(type=ChatCompletionClientBase)
        self.execution_settings = OpenAIChatPromptExecutionSettings(temperature=0, maxtokens=1000)    
        

    async def init(self):
        self.cosmosclient = CosmosClient.from_connection_string(self.COSMOS_CONNECTION_STRING)
        indexing_policy = {
            "vectorIndexes": [
                {
                    "path": "/embedding",
                    "type": "diskANN",
                    "quantizationByteSize": 96,
                    "indexingSearchListSize": 100
                }
            ]
        }
        vector_embedding_policy = { 
            "vectorEmbeddings": [ 
                { 
                    "path": "/embedding", 
                    "dataType": "float32", 
                    "distanceFunction": "cosine", 
                    "dimensions": 3072 # 1536 * 2 bytes = 3072 bytes
                }
            ]    
        }
        cosmos_container_properties = {
            "partition_key": "/key"
        } 
        self.noSqlMemoryStore = AzureCosmosDBNoSQLMemoryStore(self.cosmosclient, self.COSMOS_DATABASE, "/key", vector_embedding_policy, indexing_policy, cosmos_container_properties )
        await self.noSqlMemoryStore.create_collection(self.COSMOS_COLLECTION)
        collectionname = await self.noSqlMemoryStore.does_collection_exist(self.COSMOS_COLLECTION)
        logging.info(f"Collection {self.COSMOS_COLLECTION} is present: {collectionname}")
        self.memory = SemanticTextMemory(storage=self.noSqlMemoryStore, embeddings_generator=self.kernel.get_service("text_embedding"))
    

    async def get_correct_mail_from_msg(self,msg):
        start = time.time()
        chat_history = ChatHistory()
        prompt = f"""{prompts.PROMPT}

        {prompts.PROMPT_FOOTER}
        Titolo della mail: {msg.Oggetto}
        Contenuto della mail: {msg.Messaggio}"""

        chat_history.add_user_message(prompt)

        response = await self.chat_completion_service.get_chat_message_content(
            chat_history=chat_history,
            settings=self.execution_settings
        )
        end = time.time()
        prompt_tokens = response.metadata["usage"].prompt_tokens
        completion_tokens = response.metadata["usage"].completion_tokens
        logging.info(f"Execution time for {msg.Oggetto}: {(end-start) * 10**3} ms")
        logging.info(f"Token consumption for {msg.Oggetto} - PromptTokens: {prompt_tokens} CompletionTokens: {completion_tokens}")
        return response 

    async def get_embeddings(self,msg):
        start = time.time()
        text2search = self.truncate_tokens(string=f"{msg.Oggetto} {msg.Messaggio}", encoding_name="gpt-4-o", max_length=7800)
        embeddings = await self.memory.search(self.COSMOS_COLLECTION, text2search, limit=3)
        end = time.time()
        logging.info(f"Execution time for {msg.Oggetto}: {(end-start) * 10**3} ms")
        return embeddings
    
    def truncate_tokens(self,string: str, encoding_name: str, max_length: int = 8192) -> str:
        """Truncates a text string based on max number of tokens."""
        encoding = tiktoken.encoding_for_model(encoding_name)
        encoded_string = encoding.encode(string)
        num_tokens = len(encoded_string)

        if num_tokens > max_length:
            string = encoding.decode(encoded_string[:max_length])

        return string

    async def get_correct_mail_with_embeddings_from_msg(self, msg, embeddings):
        start = time.time()
        chat_history = ChatHistory()
        prompt = f"""{prompts.PROMPT}

        {prompts.PROMPT_EMBEDDING}

        {prompts.PROMPT_FOOTER}
        Titolo della mail: {msg.Oggetto}
        Contenuto della mail: {msg.Messaggio}

        E il risultato della ricerca vettoriale:""" 
        for results in embeddings:
            prompt = f"{prompt} \n {results.description} - {results.relevance}" 
        #debug(f"Prompt: {prompt}")
        chat_history.add_user_message(prompt)

        response = await self.chat_completion_service.get_chat_message_content(
            chat_history=chat_history,
            settings=self.execution_settings
        )
        end = time.time()
        prompt_tokens = response.metadata["usage"].prompt_tokens
        completion_tokens = response.metadata["usage"].completion_tokens
        logging.info(f"Execution time for {msg.Oggetto}: {(end-start) * 10**3} ms")
        logging.info(f"Token consumption for {msg.Oggetto} - PromptTokens: {prompt_tokens} CompletionTokens: {completion_tokens}")
        return response 