import os
from openai import OpenAI, RateLimitError, APIError, InternalServerError
from dotenv import load_dotenv
from logger import logger
load_dotenv()

def querying_with_langchain_gpt4(query):
    try:
        logger.debug(f"Query ===> {query}")
        system_rules = "I want you to act as an Indian story teller. You will come up with entertaining stories that are engaging, imaginative and captivating for children in India. It can be fairy tales, educational stories or any other type of stories which has the potential to capture children’s attention and imagination. A story should not be more than 200 words. The audience for the stories do not speak English natively. So use very simple English with short and simple sentences, no complex or compound sentences. Extra points if the story ends with an unexpected twist."
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        res = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_rules},
                {"role": "user", "content": query},
            ],
        )
        message = res.choices[0].message.model_dump()
        response = message["content"]
        logger.info({"label": "openai_response", "response": response})
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