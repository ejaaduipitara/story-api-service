FROM continuumio/anaconda3

ARG ARG_BUCKET_NAME
ARG ARG_DATABASE_NAME
ARG ARG_DATABASE_USERNAME
ARG ARG_DATABASE_PASSWORD
ARG ARG_DATABASE_IP
ARG ARG_DATABASE_PORT
ARG ARG_OPENAI_API_KEY
ARG ARG_AI4BHARAT_API_KEY

WORKDIR /root
RUN apt-get update && apt-get install -y curl file
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH=$PATH:/root/.cargo/bin \
    GOOGLE_APPLICATION_CREDENTIALS=gcp_credentials.json \
    BUCKET_NAME=$ARG_BUCKET_NAME  \
    DATABASE_NAME=$ARG_DATABASE_NAME \
    DATABASE_USERNAME=$ARG_DATABASE_USERNAME \
    DATABASE_PASSWORD=$ARG_DATABASE_PASSWORD \
    DATABASE_IP=$ARG_DATABASE_IP \
    DATABASE_PORT=$ARG_DATABASE_PORT \
    OPENAI_API_KEY=$ARG_OPENAI_API_KEY \
    AI4BHARAT_API_KEY=$ARG_AI4BHARAT_API_KEY
RUN apt-get update && apt install build-essential --fix-missing -y
RUN wget --no-check-certificate https://dl.xpdfreader.com/xpdf-tools-linux-4.04.tar.gz &&  \
    tar -xvf xpdf-tools-linux-4.04.tar.gz && cp xpdf-tools-linux-4.04/bin64/pdftotext /usr/local/bin
RUN apt-get install ffmpeg -y
COPY requirements-prod.txt /root/
RUN pip3 install -r requirements-prod.txt
COPY gcp_credentials.json main.py query_with_gptindex.py cloud_storage.py query_with_langchain.py io_processing.py translator.py database_functions.py query_with_tfidf.py Titles.csv script.sh /root/
EXPOSE 8000
ENTRYPOINT ["bash","script.sh"]