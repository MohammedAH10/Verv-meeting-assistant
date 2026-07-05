from pydantic import BaseModel
from typing import Tuple, List, Literal
from pydantic_ai import Agent
from pydantic_ai.model.anthropic import AnthropicModel
from pydantic_ai.model.groq import GroqModel
from pydantic_ai.model.openai import OpenAIModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.providers.openai import OpenAIProvider


import logging
import os
from dotenv import load_dotenv
from db import DatabaseManager
from ollama import chat, AsyncClient
import asyncio
# from ollama import AsyncClient


# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)

logger = logging.getLogger(__name__)

# load env varaiables
load_dotenv()

db = DatabaseManager()

class Block(BaseModel):
    """Represent a block of content in a section

    Block type must align with frontend rendering capabilities
    - 'text': Plain text content
    - 'bullet': Bulleted list item
    - 'heading1': Large section heading
    - 'heading2': Medium section heading

    Colors currently supported:
    - 'gray': Gray text color
    - '' or any other value: Default text color
    """

    id: str
    type: Literal['bullet', 'heading1', 'heading2', 'text']
    content: str
    color: str # Frontend currently 

class Section(BaseModel):
    """Represent a section in the meeting summary"""
    title: str
    blocks: List[Block]

class MeetingNotes(BaseModel):
    """represent meeting notes"""
    meeting_name: str
    sections: List[Section]

class People(BaseModel):
    """Represent thte people in the meeting. - Always have this part in the output: Title - Person Name (Role, Details)"""
    title: str
    block: List[Block]

class SummaryResponse(BaseModel):
    """Represents the meeting summary response base on the section of the transcript"""
    MeetingName: str
    People : People
    SessionSummary : Section
    CriticalDeadlines: Section
    KeyItemsDecisions: Section
    ImmediateActionItems: Section
    NextSteps: Section
    MeetingNotes: MeetingNotes


# ---------------------MAIN CLASS Used by main.py------------------------------------------
class TranscriptProcessor:
    """Handles the processing of meeting transcripts using AI models """
    def __init__(self) -> None:
        """Initializee the transcript processor"""
        logger.info("TrnascriptProcessor initialized")
        self.db = DatabaseManager()
        self.activate_clients = [] # Tracck active Ollama client session

    async def process_transcript(self, text: str, model: str, model_name: str, chunk_size: int= 5000, overlap: int = 1000, custom_prompt: str = "") -> Tuple[int, List[str]]:
        """
        Process transcript text into chunks and generate structured summaries for each chunk using an AI model.

        Args:
            text: The transcript text.
            model: The AI model provider ('claude', 'ollama', 'groq', 'openai').
            model_name: The specific model name.
            chunk_size: The size of each text chunk.
            overlap: The overlap between consecutive chunks.
            custom_prompt: A custom prompt to use for the AI model.

        Returns:
            A tuple containing:
            - The number of chunks processed.
            - A list of JSON strings, where each string is the summary of a chunk.
        """
        logger.info(f"Processed transcript (length {len(text)}) with model_provider={model}, model_name={model_name}, chunksize={chunk_size}, overlap={overlap}.")

        all_json_data = []
        agent = None # Define agent  variable
        llm = None # define llm varaible

        try:
            # select and initialize the AI model and Agent
            if model == "claude":
                api_key = await db.get_api_key("claude")
                if not api_key:
                    raise ValueError("ANTHROPIC_API_KEY environments variable is not set")
                llm = AnthropicModel(model_name, provider=AnthropicProvider(api_key=api_key))
                logger.info(f"Using Claude model: {model_name}")

            elif model == "ollama":
                # use env variable for ollama host configuration
                ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
                ollama_base_url = f"{ollama_host}/v1"
                ollama_model = OpenAIModel(model_name=model_name, provider=OpenAIProvider(base_url=ollama_base_url))
                llm = ollama_model
                if model_name.lower().startswith("phi4") or model_name.lower().startswith("llama"):
                    chunk_size = 10000
                    overlap = 1000
                else:
                    chunk_size = 30000
                    overlap = 1000
                logger.info(f"Using Ollama model: {model_name}")

            elif model == 'groq':
                api_key = await db.get_api_key("groq")
                if not api_key:
                    raise ValueError("GROQ_API_KEY environment variable is not set")
                llm = GroqModel(model_name, provider=GroqProvider(api_key=api_key))
                logger.info(f"Using Groq mdoel: {model_name}")
            # ------ADD OPENAI SUPPORT HERE
            elif model == "openai":
                api_key = await db.get_api_key("openai")
                if not api_key:
                    raise ValueError("OPENAI_API_KEY environment variable is not set")
                llm = OpenAIModel(model_name, provider=OpenAIProvider(api_key=api_key))
                logger.info(f"Using openai model: {model_name}")

            else:
                logger.error(f"Unsupported model provider requested: {model}")
                raise ValueError(f"Unsupported model provider: {model}")


            # Initialize agent with selected llm
            agent = Agent(
                llm,
                result_type = SummaryResponse,
                result_retries = 2,
            )
            logger.info("Pydantic AI Agent Initialized")
            