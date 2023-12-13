import os.path
from enum import Enum
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from io_processing import *
from query_with_langchain import *
from cloud_storage_oci import *
from logger import logger

api_description = """
"""

app = FastAPI(title="Story API Service",
              description=api_description,
              version="1.0.0",
              terms_of_service="http://example.com/terms/",
              contact={
                 
              },
              license_info={
                  "name": "MIT License",
                  "url": "https://www.jugalbandi.ai/",
              }, )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class ResponseForAudio(BaseModel):
    query: str = None
    query_in_english: str = None
    answer: str = None
    answer_in_english: str = None
    audio_output_url: str = None
    source_text: str = None

class DropdownOutputFormat(str, Enum):
    TEXT = "Text"
    VOICE = "Voice"

class DropDownInputLanguage(str, Enum):
    en = "English"
    bn = "Bengali"
    gu = "Gujarati"
    hi = "Hindi"
    kn = "Kannada"
    ml = "Malayalam"
    mr = "Marathi"
    ori = "Oriya"
    pa = "Punjabi"
    ta = "Tamil"
    te = "Telugu"

class HealthCheck(BaseModel):
    """Response model to validate and return when performing a health check."""

    status: str = "OK"


@app.get("/")
async def root():
    return {"message": "Welcome to Jugalbandi API"}

@app.get(
    "/health",
    tags=["Health Check"],
    summary="Perform a Health Check",
    response_description="Return HTTP Status Code 200 (OK)",
    status_code=status.HTTP_200_OK,
    response_model=HealthCheck,
    include_in_schema=True
)
def get_health() -> HealthCheck:
    """
    ## Perform a Health Check
    Endpoint to perform a healthcheck on. This endpoint can primarily be used Docker
    to ensure a robust container orchestration and management is in place. Other
    services which rely on proper functioning of the API service will not deploy if this
    endpoint returns any other HTTP status code except 200 (OK).
    Returns:
        HealthCheck: Returns a JSON response with the health status
    """
    return HealthCheck(status="OK")

@app.get("/query-using-voice", tags=["Q&A over Document Store"])
async def query_with_voice_input(input_language: DropDownInputLanguage,
                                 output_format: DropdownOutputFormat, query_text: str = "",
                                 audio_url: str = "") -> ResponseForAudio:
    load_dotenv()
    language = 'or' if input_language.name == DropDownInputLanguage.ori.name else input_language.name
    is_audio = False
    text = None
    regional_answer = None
    answer = None
    audio_output_url = None
    source_text = None
    logger.info({"label": "query", "query_text":query_text,"input_language": input_language, "output_format": output_format, "audio_url": audio_url})
    if query_text == "" and audio_url == "":
        query_text = None
        error_message = "Either 'Query Text' or 'Audio URL' should be present"
        status_code = 422
    else:
        if query_text != "":
            text, error_message = process_incoming_text(query_text, language)
            if output_format.name == "VOICE":
                is_audio = True
        else:
            query_text, text, error_message = process_incoming_voice(audio_url, language)
            is_audio = True

        if text is not None:
            answer, source_text, paraphrased_query, error_message, status_code = querying_with_langchain_gpt4(text)
            if answer is not None:
                regional_answer, error_message = process_outgoing_text(answer, language)
                if regional_answer is not None:
                    if is_audio:
                        output_file, error_message = process_outgoing_voice(regional_answer, language)
                        if output_file is not None:
                            upload_file_object(output_file.name)
                            audio_output_url, error_message = give_public_url(output_file.name)
                            logger.debug(f"Audio Ouput URL ===> {audio_output_url}")
                            output_file.close()
                            os.remove(output_file.name)
                        else:
                            status_code = 503
                    else:
                        audio_output_url = ""
                else:
                    status_code = 503
        else:
            status_code = 503

    if status_code != 200:
        logger.error({"query":query_text, "input_language": input_language, "output_format": output_format, "audio_url": audio_url, "status_code": status_code, "error_message": error_message})
        raise HTTPException(status_code=status_code, detail=error_message)

    response = ResponseForAudio()
    response.query = query_text
    response.query_in_english = text
    response.answer = regional_answer
    response.answer_in_english = answer
    response.audio_output_url = audio_output_url
    response.source_text = source_text
    logger.info(msg=response)
    return response