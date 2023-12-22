import os.path
from enum import Enum

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from cloud_storage_oci import *
from io_processing import *
from query_with_langchain import *
from telemetry_middleware import TelemetryMiddleware
from utils import *

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

class DropdownOutputFormat(str, Enum):
    TEXT = "text"
    AUDIO = "audio"

class DropDownInputLanguage(str, Enum):
    en = "en"
    bn = "bn"
    gu = "gu"
    hi = "hi"
    kn = "kn"
    ml = "ml"
    mr = "mr"
    ori = "or"
    pa = "pa"
    ta = "ta"
    te = "te"

class OutputResponse(BaseModel):
    text: str
    audio: str = None
    language: DropDownInputLanguage
    format: DropdownOutputFormat

class ResponseForQuery(BaseModel):
    output: OutputResponse
    
class HealthCheck(BaseModel):
    """Response model to validate and return when performing a health check."""

    status: str = "OK"

class QueryInputModel(BaseModel):
    language: DropDownInputLanguage
    text:str = None
    audio:str = None

class QueryOuputModel(BaseModel):
    format: DropdownOutputFormat

class QueryModel(BaseModel):
    input: QueryInputModel
    output: QueryOuputModel

# Telemetry API logs middleware
app.add_middleware(TelemetryMiddleware)

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

@app.post("/v1/query", tags=["Q&A over Document Store"])
async def query(request: QueryModel) -> ResponseForQuery:
    load_dotenv()
    language = 'or' if request.input.language.name == DropDownInputLanguage.ori.name else request.input.language.name
    output_format = request.output.format.name
    audio_url = request.input.audio
    query_text = request.input.text
    is_audio = False
    text = None
    regional_answer = None
    answer = None
    audio_output_url = None
    source_text = None
    logger.info({"label": "query", "query_text":query_text,"input_language": language, "output_format": output_format, "audio_url": audio_url})
    if query_text is None and audio_url is None:
        query_text = None
        error_message = "Either 'Query text' or 'audio' should be present"
        status_code = 422
    else:
        if query_text is not None:
            text, error_message = process_incoming_text(query_text, language)
            if output_format == "AUDIO":
                is_audio = True
        else:
            if not is_url(audio_url) and not is_base64(audio_url):
                logger.error({"query":query_text, "input_language": language, "output_format": output_format, "audio_url": audio_url, "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY, "error_message": "Invalid audio input!"})
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid audio input!")
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
                        audio_output_url = None
                else:
                    status_code = 503
        else:
            status_code = 503

    if status_code != 200:
        logger.error({"query":query_text, "input_language": language, "output_format": output_format, "audio_url": audio_url, "status_code": status_code, "error_message": error_message})
        raise HTTPException(status_code=status_code, detail=error_message)

    response = ResponseForQuery(output=OutputResponse(text=regional_answer, audio=audio_output_url, language=language, format=output_format.lower()))
    logger.info(response)
    return response
    