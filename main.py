import os.path
from enum import Enum
from typing import List
from cachetools import TTLCache
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from database_functions import *
from io_processing import *
from query_with_gptindex import *
from query_with_langchain import *
from cloud_storage import *
import uuid
import shutil
from zipfile import ZipFile
from query_with_tfidf import querying_with_tfidf
from fastapi.responses import Response

from sse_starlette.sse import EventSourceResponse

api_description = """
Jugalbandi.ai has a vector datastore that allows you to get factual Q&A over a document set.

API is currently available in it's alpha version. We are currently gaining test data to improve our systems and 
predictions. 🚀

## Factual Q&A over large documents

You will be able to:

* **Upload documents** (_implemented_).
Allows you to upload documents and create a vector space for semantic similarity search. Basically a better search 
than Ctrl+F

* **Factual Q&A** (_implemented_).
Allows you to pass uuid for a document set and ask a question for factual response over it.
"""

app = FastAPI(title="Jugalbandi.ai",
              description=api_description,
              version="0.0.1",
              terms_of_service="http://example.com/terms/",
              contact={
                  "name": "Karanraj - Major contributor in Jugalbandi.ai",
                  "email": "karanraj.m@thoughtworks.com",
              },
              license_info={
                  "name": "MIT License",
                  "url": "https://www.jugalbandi.ai/",
              }, )
ttl = int(os.environ.get("CACHE_TTL", 86400)) 
cache = TTLCache(maxsize=100, ttl=ttl)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Response(BaseModel):
    query: str = None
    answer: str = None
    source_text: str = None


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
    hi = "Hindi"
    kn = "Kannada"
    te = "Telugu"
    


@app.get("/")
async def root():
    return {"message": "Welcome to Jugalbandi API"}


@app.get("/query-with-gptindex", tags=["Q&A over Document Store"])
async def query_using_gptindex(uuid_number: str, query_string: str) -> Response:

    # lowercase_query_string = query_string.lower()
    # if lowercase_query_string in cache:
    #     print("Value in cache", lowercase_query_string)
    #     return cache[lowercase_query_string]
    # else:
        # print("Value not in cache", lowercase_query_string)
        load_dotenv()
        answer, source_text, error_message, status_code = querying_with_gptindex(uuid_number, query_string)
        engine = await create_engine()
        await insert_qa_logs(engine=engine, model_name="gpt-index", uuid_number=uuid_number, query=query_string,
                            paraphrased_query=None, response=answer, source_text=source_text, error_message=error_message)
        await engine.close()

        if status_code != 200:
            print("Error status code", status_code)
            print("Error message", error_message)
            raise HTTPException(status_code=status_code, detail=error_message)

        response = Response()
        response.query = query_string
        response.answer = answer
        response.source_text = source_text
        # cache[lowercase_query_string] = response
        return response


@app.get("/query-with-langchain", tags=["Q&A over Document Store"])
async def query_using_langchain(uuid_number: str, query_string: str) -> Response:
    lowercase_query_string = query_string.lower() + uuid_number
    if lowercase_query_string in cache:
        print("Value in cache", lowercase_query_string)
        return cache[lowercase_query_string]
    else:
        print("Value not in cache", lowercase_query_string)
        load_dotenv()
        answer, source_text, paraphrased_query, error_message, status_code = querying_with_langchain(uuid_number,
                                                                                                    query_string)
        print(engine, "langchain", uuid_number, query_string, paraphrased_query, answer, source_text,)
        if status_code != 200:
            raise HTTPException(status_code=status_code, detail=error_message)

        response = Response()
        response.query = query_string
        response.answer = answer
        response.source_text = source_text
        cache[lowercase_query_string] = response
        return response


@app.post("/upload-files", tags=["Document Store"])
async def upload_files(description: str, files: List[UploadFile] = File(...)):
    load_dotenv()
    uuid_number = str(uuid.uuid1())
    os.makedirs(uuid_number)
    files_list = []
    for file in files:
        try:
            contents = file.file.read()
            with open(file.filename, 'wb') as f:
                f.write(contents)
        except OSError:
            return "There was an error uploading the file(s)"
        finally:
            if ".zip" in file.filename:
                os.makedirs("temp_archive")
                with ZipFile(file.filename, 'r') as zip_ref:
                    zip_ref.extractall("temp_archive")
                bad_zip_folder = "temp_archive/__MACOSX"
                if os.path.exists(bad_zip_folder):
                    shutil.rmtree(bad_zip_folder)
                archived_files = os.listdir("temp_archive")
                files_list.extend(archived_files)
                for archived_file in archived_files:
                    shutil.move("temp_archive/" + archived_file, archived_file)
                    upload_file(uuid_number, archived_file)
                    shutil.move(archived_file, uuid_number + "/" + archived_file)
                shutil.rmtree("temp_archive")
                os.remove(file.filename)
            else:
                files_list.append(file.filename)
                upload_file(uuid_number, file.filename)
                file.file.close()
                shutil.move(file.filename, uuid_number + "/" + file.filename)

    error_message, status_code = gpt_indexing(uuid_number)
    if status_code == 200:
        error_message, status_code = langchain_indexing(uuid_number)

    engine = await create_engine()
    await insert_document_store_logs(engine=engine, description=description, uuid_number=uuid_number,
                                     documents_list=files_list, error_message=error_message)
    await engine.close()

    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=error_message)

    index_files = ["index.json", "index.faiss", "index.pkl"]
    for index_file in index_files:
        upload_file(uuid_number, index_file)
        os.remove(index_file)
    shutil.rmtree(uuid_number)
    return {"uuid_number": str(uuid_number), "message": "Files uploading is successful"}


@app.get("/query-using-voice", tags=["Q&A over Document Store"])
async def query_with_voice_input(uuid_number: str, input_language: DropDownInputLanguage,
                                 output_format: DropdownOutputFormat, query_text: str = "",
                                 audio_url: str = "") -> ResponseForAudio:
    load_dotenv()
    language = input_language.name
    output_medium = output_format.name
    is_audio = False
    text = None
    paraphrased_query = None
    regional_answer = None
    answer = None
    audio_output_url = None
    source_text = None

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
            output_medium = "VOICE"
            is_audio = True

        if text is not None:
            print(text)
            answer, source_text, paraphrased_query, error_message, status_code = querying_with_langchain_gpt4(uuid_number,
                                                                                                         text)
            if answer is not None:
                regional_answer, error_message = process_outgoing_text(answer, language)
                if regional_answer is not None:
                    if is_audio:
                        output_file, error_message = process_outgoing_voice(regional_answer, language)
                        if output_file is not None:
                            upload_file("output_audio_files", output_file.name)
                            audio_output_url = give_public_url(output_file.name)
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

    engine = await create_engine()
    await insert_qa_voice_logs(engine=engine, uuid_number=uuid_number, input_language=input_language.value,
                               output_format=output_medium, query=query_text, query_in_english=text,
                               paraphrased_query=paraphrased_query, response=regional_answer,
                               response_in_english=answer,
                               audio_output_link=audio_output_url, source_text=source_text, error_message=error_message)
    await engine.close()
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=error_message)

    response = ResponseForAudio()
    response.query = query_text
    response.query_in_english = text
    response.answer = regional_answer
    response.answer_in_english = answer
    response.audio_output_url = audio_output_url
    response.source_text = source_text
    return response


@app.get("/rephrased-query")
async def get_rephrased_query(query_string: str):
    load_dotenv()
    answer = rephrased_question(query_string)
    return {"given_query": query_string, "rephrased_query": answer}


@app.post("/source-document", tags=["Source Document over Document Store"])
async def get_source_document(query_string: str = "", input_language: DropDownInputLanguage = DropDownInputLanguage.en,
                              audio_file: UploadFile = File(None)):
    load_dotenv()
    filename = ""
    if audio_file is not None:
        try:
            contents = audio_file.file.read()
            with open(audio_file.filename, 'wb') as f:
                f.write(contents)
            filename = audio_file.filename
        except OSError:
            return "There was an parsing the audio file"
    answer = querying_with_tfidf(query_string, input_language.name, filename)
    return answer


@app.get("/query-with-langchain-gpt4", tags=["Q&A over Document Store"])
async def query_using_langchain_with_gpt4(uuid_number: str, query_string: str) -> Response:
    lowercase_query_string = query_string.lower() + uuid_number
    if lowercase_query_string in cache:
        print("Value in cache", lowercase_query_string)
        return cache[lowercase_query_string]
    else:
        load_dotenv()
        answer, source_text, paraphrased_query, error_message, status_code = querying_with_langchain_gpt4(uuid_number,
                                                                                                        query_string)

        if status_code != 200:
            raise HTTPException(status_code=status_code, detail=error_message)

        response = Response()
        response.query = query_string
        response.answer = answer
        response.source_text = source_text
        cache[lowercase_query_string] = response
        return response

@app.get("/query-with-langchain-gpt4_streaming", tags=["Q&A over Document Store"])
async def query_using_langchain_with_gpt4_streaming(uuid_number: str, query_string: str) -> EventSourceResponse:
    lowercase_query_string = "streaming_" + query_string.lower() + uuid_number
    if lowercase_query_string in cache:
        print("Value in cache", lowercase_query_string)
        return cache[lowercase_query_string]
    else:
        load_dotenv()
        response = querying_with_langchain_gpt4_streaming(uuid_number, query_string)

        if isinstance(response, EventSourceResponse):
            # If the response is already a StreamingResponse, return it directly
            return response

        # print(response)

        if response.status_code != 200:
            # If there's an error, raise an HTTPException
            raise HTTPException(status_code=response.status_code, detail=response.text)

        # Retrieve the response content
        # response_content = await response.content.read()

        # Create a StreamingResponse with the response content
        streaming_response = EventSourceResponse(
            response.content,
            headers={"Content-Type":"text/plain"}
        )

        # Set the response headers
        for header, value in response.headers.items():
            streaming_response.headers[header] = value

        # Store the streaming_response object in the cache
        cache[lowercase_query_string] = streaming_response

        return streaming_response