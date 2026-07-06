from string import Formatter
import time
import json
import uvicorn
import logging
from fastapi import FastAPI, HTTPExceptions, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv
from db import DatabaseManager
from threading import Lock
from transcript_processor import TranscriptProcessor


# load env varaibles
load_dotenv()

# configure logger with line numbers and function names
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# create console handler with formatting
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# create formatter with line numbers and function names
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d - %(funcName)s()] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler.setFormatter(formatter)

# Add handler to logger if not already addded
if not logger.handlers:
    logger.addHandler(console_handler)


app = FastAPI(
    title="Meeting Summarizer API",
    description="API for processing and summarizing meetig transcripts",
    version="1.0.0"
)

# configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],     # Allow all methods
    allow_headers=["*"],     #Allow all headers
    max_age=3600,            # cache preflight requests for 1 hour
)

# global database manager instance for meeting management endpoints
db = DatabaseManager()

# New pydantic models for meeting management
class Transcript(BaseModel):
    id: str
    text: str
    timestamp: str
    # recording relative timestamps for audio-transcript synchronization
    audio_start_time: Optional[float] = None
    audio_end_time: Optional[float] = None
    duration: Optional[float] = None

class MeetingResponse(BaseModel):
    id: str
    title: str


class MeetingDetailsResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    transcripts: List[Transcript]


class MeetingTitleUpdate(BaseModel):
    meeting_id: str
    title: str


class DeleteMeetingRequest(BaseModel):
    meeting_id: str


class SaveTranscriptRequest(BaseModel):
    meeting_title: str
    transcripts: List[Transcript]
    folder_path: Optional[str] = None # NEW: path to meeting folder (for new folder structure)


class SaveModelConfigRequest(BaseModel):
    provider: str
    model: str
    whisperModel: str
    apiKey: Optional[str] = None 


class SaveTranscriptConfigRequest(BaseModel):
    provider: str
    model: str
    apiKey: Optional[str] = None 


class TrascriptRequest(BaseModel):
    """Request model for transcript text, updated with meeting_id"""
    text: str
    model: str
    model_name: str
    meeting_id: str
    chunk_size: Optional[int] = 5000
    overlap: Optional[int] = 1000
    custom_prompt: Optional[str] = "Generate a summary of the meeting transcript."

class SummaryProcessor:
    """Handles the processing of the summariess in the thread-safe way"""
    def __init__(self):
        try:
            self.db = DatabaseManager()

            logger.info("Initializing SummaryProcessor components")
            self.transcript_processor = TranscriptProcessor()
            logger.info("SummaryProcessor initialized successfully (core components)")
        except Exception as e:
            logger.error(f"Failed to initialized SummaryProcessor: {str(e)}", exc_info=True)
            raise 

    async def process_transcript(self, text: str, model: str, model_name: str, chunk_size: int = 5000,
        overlap: int = 1000, custom_prompt: str = "Generate a summary of the meeting transcript") -> tuple:
            """Process a transcript text"""
            try:
                if not text:
                    raise ValueError("Empty transcript text provided")

                # Validate chunk_size and overlap 
                if chunk_size <= 0:
                    raise ValueError("Chunk_size must be positive")
                if overlap < 0:
                    raise ValueError("overlap must be non-negative")
                if overlap >=chunk_size:
                    overlap = chunk_size - 1 # Ensure overlap is less than chunk_size 

                # Ensure step size is positive
                step_size = chunk_size - overlap
                if step_size <= 0:
                    chunk_size = overlap + 1 # Adjust chunk_size to ensure positive step

                logger.info(f"Processing transcript of length {len(text)} with chunk_size = {chunk_size}, overlap = {overlap}")
                num_chunks, all_json_data = await self.transcript_processor.process_transcript(
                    text=text,
                    model=model,
                    model_name=model_name,
                    chunk_size=chunk_size,
                    overlap=overlap,
                    custom_prompt=custom_prompt
                )
                logger.info(f"Successfully processed transcript into {num_chunks} chunks")

                return num_chunks, all_json_data
            except Exception as e:
                logger.error(f"Error processing transcript: {str(e)}", exc_info=True)
                raise

    def cleanup(self):
        """Cleanup resources"""
        try:
            logger.info("Cleaning up resources")
            if hasattr(self, 'transcript_processor'):
                self.transcript_processor.cleanup()
            logger.info("Cleanup completed successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}", exc_info=True)

