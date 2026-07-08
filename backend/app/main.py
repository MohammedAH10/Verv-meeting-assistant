from string import Formatter
import time
import json
import uvicorn
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
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


class TranscriptRequest(BaseModel):
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

# Inititlaize processor
processor = SummaryProcessor()

# new meeting management endpoints
@app.get("/get-meetings", response_model=List[MeetingResponse])
async def get_meetings():
    """Get all meetings with their basic information"""
    try:
        meetings = await db.get_all_meetings()
        return [{"id": meeting["id"], "title": meeting["title"]} for meeting in meetings]
    except Exception as e:
        logger.error(f"Error getting meetings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-meeting/{meeting_id}", response_model=MeetingDetailsResponse)
async def get_meeting(meeting_id: str):
    """Get specific meeting by ID with all its details"""
    try:
        meeting = await db.get_meeting(meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        return meeting
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting meeting {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))       

@app.post("/save-meeeting-title")
async def save_meeting_title(data: MeetingTitleUpdate):
    """ Save meeting title"""
    try:
        await db.update_meeting_title(data.meeeting_id, data.title)
        return {"message": "Meeting title saved successfully"}
    except Exception as e:
        logger.error(f"Error saving meeting title: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/delete-meeting")
async def delete_meeting(data: DeleteMeetingRequest):
    """Delete a meeting and all its associated data"""
    try:
        success = await db.delete_meeting(data.meeting_id)
        if success:
            return {'message': 'Meeting deleted successfully'}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete meeting")
    
    except Exceptions as e:
        logger.error(f"Erro deleting meeting: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

async def process_transcript_background(process_id: str, transcript: TranscriptRequest, custom_prompt: str):
    """Background task to process transcript"""
    try:
        logger.info(f"Starting background processing for process_id: {process_id}")
        
        # Early validation for common issues
        if not transcript.text or not transcript.text.strip():
            raise ValueError("Empty transcript text provided")
        
        if transcript.model in ["claude", "groq", "openai"]:
            # Check if API key is available for cloud providers
            api_key = await processor.db.get_api_key(transcript.model)
            if not api_key:
                provider_names = {"claude": "Anthropic", "groq": "Groq", "openai": "OpenAI"}
                raise ValueError(f"{provider_names.get(transcript.model, transcript.model)} API key not configured. Please set your API key in the model settings.")

        _, all_json_data = await processor.process_transcript(
            text=transcript.text,
            model=transcript.model,
            model_name=transcript.model_name,
            chunk_size=transcript.chunk_size,
            overlap=transcript.overlap,
            custom_prompt=custom_prompt
        )

        # Create final summary structure by aggregating chunk results
        final_summary = {
            "MeetingName": "",
            "People": {"title": "People", "blocks": []},
            "SessionSummary": {"title": "Session Summary", "blocks": []},
            "CriticalDeadlines": {"title": "Critical Deadlines", "blocks": []},
            "KeyItemsDecisions": {"title": "Key Items & Decisions", "blocks": []},
            "ImmediateActionItems": {"title": "Immediate Action Items", "blocks": []},
            "NextSteps": {"title": "Next Steps", "blocks": []},
            # "OtherImportantPoints": {"title": "Other Important Points", "blocks": []},
            # "ClosingRemarks": {"title": "Closing Remarks", "blocks": []},
            "MeetingNotes": {
                "meeting_name": "",
                "sections": []
            }
        }

        # Process each chunk's data
        for json_str in all_json_data:
            try:
                json_dict = json.loads(json_str)
                if "MeetingName" in json_dict and json_dict["MeetingName"]:
                    final_summary["MeetingName"] = json_dict["MeetingName"]
                for key in final_summary:
                    if key == "MeetingNotes" and key in json_dict:
                        # Handle MeetingNotes sections
                        if isinstance(json_dict[key].get("sections"), list):
                            # Ensure each section has blocks array
                            for section in json_dict[key]["sections"]:
                                if not section.get("blocks"):
                                    section["blocks"] = []
                            final_summary[key]["sections"].extend(json_dict[key]["sections"])
                        if json_dict[key].get("meeting_name"):
                            final_summary[key]["meeting_name"] = json_dict[key]["meeting_name"]
                    elif key != "MeetingName" and key in json_dict and isinstance(json_dict[key], dict) and "blocks" in json_dict[key]:
                        if isinstance(json_dict[key]["blocks"], list):
                            final_summary[key]["blocks"].extend(json_dict[key]["blocks"])
                            # Also add as a new section in MeetingNotes if not already present
                            section_exists = False
                            for section in final_summary["MeetingNotes"]["sections"]:
                                if section["title"] == json_dict[key]["title"]:
                                    section["blocks"].extend(json_dict[key]["blocks"])
                                    section_exists = True
                                    break
                            
                            if not section_exists:
                                final_summary["MeetingNotes"]["sections"].append({
                                    "title": json_dict[key]["title"],
                                    "blocks": json_dict[key]["blocks"].copy() if json_dict[key]["blocks"] else []
                                })
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON chunk for {process_id}: {e}. Chunk: {json_str[:100]}...")
            except Exception as e:
                logger.error(f"Error processing chunk data for {process_id}: {e}. Chunk: {json_str[:100]}...")

        # Update database with meeting name using meeting_id
        if final_summary["MeetingName"]:
            await processor.db.update_meeting_name(transcript.meeting_id, final_summary["MeetingName"])

        # Save final result
        if all_json_data:
            await processor.db.update_process(process_id, status="completed", result=json.dumps(final_summary))
            logger.info(f"Background processing completed for process_id: {process_id}")
        else:
            error_msg = "Summary generation failed: No chunks were processed successfully. Check logs for specific errors."
            await processor.db.update_process(process_id, status="failed", error=error_msg)
            logger.error(f"Background processing failed for process_id: {process_id} - {error_msg}")

    except ValueError as e:
        # Handle specific value errors (like API key issues)
        error_msg = str(e)
        logger.error(f"Configuration error in background processing for {process_id}: {error_msg}", exc_info=True)
        try:
            await processor.db.update_process(process_id, status="failed", error=error_msg)
        except Exception as db_e:
            logger.error(f"Failed to update DB status to failed for {process_id}: {db_e}", exc_info=True)
    except Exception as e:
        # Handle all other exceptions
        error_msg = f"Processing error: {str(e)}"
        logger.error(f"Error in background processing for {process_id}: {error_msg}", exc_info=True)
        try:
            await processor.db.update_process(process_id, status="failed", error=error_msg)
        except Exception as db_e:
            logger.error(f"Failed to update DB status to failed for {process_id}: {db_e}", exc_info=True)


@app.post("/process-transcript")
async def process_transcript_api(transcript: TranscriptRequest, backgrround_tasks: BackgroundTasks):
    """ Process a transcript text with background processing"""
    try:
        # create new process linked to meeting_id
        process_id = await processor.db.create_process(transcript.meeting_id)

        # save transcript data associated with meeting_id
        await processor.db.save_transcript(
            transcript.meeting_id,
            transcript.text,
            transcript.model,
            transcript.model_name,
            transcript.chunk_size,
            transcript.overlap
        )

        custom_prompt  = trnascript.custom_prompt


        # Start background processing 
        background_tasks.add_task(
            process_transcript_background,
            process_id,
            transcript,
            custom_prompt
        )

        return JSONResponse({
            "message": "processingg started",
            "process_id": process_id
        })

    except Exeption as e:
        logger.error(f"Error in process_transcript_api: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))