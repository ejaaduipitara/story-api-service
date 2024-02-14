import os
from typing import (
    Any,
    List,
    Tuple
)
import openai
from openai import AzureOpenAI, RateLimitError, APIError, InternalServerError
# from openai.types import ModerationCreateResponse
import marqo
from langchain.docstore.document import Document
from langchain.vectorstores.marqo import Marqo
from dotenv import load_dotenv
from logger import logger
from config_util import get_config_value

load_dotenv()
llm_type = get_config_value("llm", "llm_type", None).lower()

if llm_type == "azure":
    client = AzureOpenAI(
        azure_endpoint=os.environ["OPENAI_API_BASE"],
        api_key=os.environ["OPENAI_API_KEY"],
        api_version=os.environ["OPENAI_API_VERSION"]
    )
elif llm_type == "openai":
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

marqo_url = get_config_value("database", "MARQO_URL", None)
marqoClient = marqo.Client(url=marqo_url)

def querying_with_langchain_gpt4(query):
    try:
        logger.debug(f"Query ===> {query}")
        system_rules = get_config_value("llm", "story_prompt", "")
        gpt_model = get_config_value("llm", "gpt_model", None)
        res = client.chat.completions.create(
            model=gpt_model,
            messages=[
                {"role": "system", "content": system_rules},
                {"role": "user", "content": query},
            ],
        )
        message = res.choices[0].message.model_dump()
        response = message["content"]
        logger.info({"label": "openai_response", "response": response})
        # response, error_message = moderate_text(response)
        # if error_message is not None:
        #     return None, None, None, error_message, 500
        # else:
        return response, "", "", None, 200
    except RateLimitError as e:
        error_message = f"OpenAI API request exceeded rate limit: {e}"
        status_code = 500
    except (APIError, InternalServerError):
        error_message = "Server is overloaded or unable to answer your request at the moment. Please try again later"
        status_code = 503
    except Exception as e:
        error_message = str(e.__context__) + " and " + e.__str__()
        status_code = 500
    return None, None, None, error_message, status_code

# def moderate_text(text:str):
#     """
#     Moderates the provided text using the OpenAI API.
#
#     Args:
#         text: The text to be moderated.
#
#     Returns:
#         A dictionary containing the moderation results and errors.
#     """
#
#     try:
#         # Send moderation request
#         response: ModerationCreateResponse = client.moderations.create(input=text)
#         result = response.results[0]
#         logger.info({"label": "openai_moderation", "response": result})
#         if result.flagged:
#             text = "As the Sakhi Virtual Assistant, I'm dedicated to providing informative and supportive assistance related to Activities, Stories, Songs, Riddles and Rhymes suitable for 3-8 year old children. Your question has been identified as inappropriate due to its harassment and violent threat content. I encourage a respectful and constructive dialogue focused on educational matters. How can I assist you further with your queries?"
#         return text, None
#     except Exception as e:
#         error_message = str(e.__context__) + " and " + e.__str__()
#         logger.error(f"Error moderating text: {error_message}")
#         return None, error_message

def query_rstory_gpt3(index_id, query):
    load_dotenv()
    logger.debug(f"Query ===> {query}")
    gpt_model = get_config_value("llm", "gpt_model", None)

    intent_response = "No"
    enable_bot_intent = get_config_value("llm", "enable_bot_intent", None)

    if enable_bot_intent.lower() == "true":
        # intent recognition using AI
        intent_system_rules = get_config_value("llm", "intent_prompt", None)
        logger.debug(f"intent_system_rules: {intent_system_rules}")
        if intent_system_rules:
            intent_res = client.chat.completions.create(
                model=gpt_model,
                messages=[
                    {"role": "system", "content": intent_system_rules},
                    {"role": "user", "content": query}
                ],
            )
            intent_message = intent_res.choices[0].message.model_dump()
            intent_response = intent_message["content"]
            logger.info({"label": "openai_intent_response", "intent_response": intent_response})

    if intent_response.lower() == "yes":
        system_rules = get_config_value("llm", "bot_prompt", "")
        logger.debug("==== System Rules ====")
        logger.debug(f"System Rules : {system_rules}")
        res = client.chat.completions.create(
            model=gpt_model,
            messages=[
                {"role": "system", "content": system_rules},
                {"role": "user", "content": query}
            ],
        )
        message = res.choices[0].message.model_dump()
        response = message["content"]
        logger.info({"label": "openai_bot_response", "bot_response": response})
        return response, None, 200
    else:
        try:
            search_index = Marqo(marqoClient, index_id, searchable_attributes=["text"])
            top_docs_to_fetch = get_config_value("database", "top_docs_to_fetch", None)
            documents = search_index.similarity_search_with_score(query, k=20)
            logger.debug(f"Marqo documents : {str(documents)}")
            min_score = get_config_value("database", "docs_min_score", None)
            filtered_document = get_score_filtered_documents(documents, float(min_score))
            filtered_document = filtered_document[:int(top_docs_to_fetch)]
            logger.info(f"Score filtered documents : {str(filtered_document)}")
            contexts = get_formatted_documents(filtered_document)
            if not documents or not contexts:
                return "I'm sorry, but I don't have enough information to provide a specific answer for your question. Please provide more information or context about what you are referring to.", None, 200
            system_rules = get_config_value("llm", "r_story_prompt", "")
            system_rules = system_rules.format(contexts=contexts)
            logger.info("==== System Rules ====")
            logger.debug(system_rules)

            res = client.chat.completions.create(
                model=gpt_model,
                messages=[
                    {"role": "system", "content": system_rules},
                    {"role": "user", "content": query},
                ],
            )
            message = res.choices[0].message.model_dump()
            response = message["content"]
            logger.info({"label": "openai_response", "response": response})
            # response, error_message = moderate_text(response)
            # if error_message is not None:
            #     return "", error_message, 500
            return response, None, 200
        except RateLimitError as e:
            error_message = f"OpenAI API request exceeded rate limit: {e}"
            status_code = 500
        except (APIError, InternalServerError):
            error_message = "Server is overloaded or unable to answer your request at the moment. Please try again later"
            status_code = 503
        except Exception as e:
            error_message = str(e.__context__) + " and " + e.__str__()
            status_code = 500
        return "", error_message, status_code


def get_score_filtered_documents(documents: List[Tuple[Document, Any]], min_score=0.0):
    return [(document, search_score) for document, search_score in documents if search_score > min_score]


def get_formatted_documents(documents: List[Tuple[Document, Any]]):
    sources = ""
    for document, _ in documents:
        sources += f"""
            > {document.page_content} \n > context_source: [filename# {document.metadata['file_name']},  page# {document.metadata['page_label']}]\n\n
            """
    return sources


def generate_source_format(documents: List[Tuple[Document, Any]]) -> str:
    """Generates an answer format based on the given data.

    Args:
    data: A list of tuples, where each tuple contains a Document object and a
        score.

    Returns:
    A string containing the formatted answer, listing the source documents
    and their corresponding pages.
    """
    try:
        sources = {}
        for doc, _ in documents:
            file_name = doc.metadata['file_name']
            page_label = doc.metadata['page_label']
            sources.setdefault(file_name, []).append(page_label)

        answer_format = "\nSources:\n"
        counter = 1
        for file_name, pages in sources.items():
            answer_format += f"{counter}. {file_name} - (Pages: {', '.join(pages)})\n"
            counter += 1
        return answer_format
    except Exception as e:
        error_message = "Error while preparing source markdown"
        logger.error(f"{error_message}: {e}", exc_info=True)
        return ""


def concatenate_elements(arr):
    # Concatenate elements from index 1 to n
    separator = ': '
    result = separator.join(arr[1:])
    return result

