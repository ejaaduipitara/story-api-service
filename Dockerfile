FROM continuumio/anaconda3:2023.03-1

WORKDIR /root
RUN apt-get update && apt-get install -y curl file
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH=$PATH:/root/.cargo/bin \
    GOOGLE_APPLICATION_CREDENTIALS=gcp_credentials.json \
    BUCKET_NAME=$BUCKET_NAME  \
    DATABASE_NAME=$DATABASE_NAME \
    DATABASE_USERNAME=$DATABASE_USERNAME \
    DATABASE_PASSWORD=$DATABASE_PASSWORD \
    DATABASE_IP=$DATABASE_IP \
    DATABASE_PORT=$DATABASE_PORT \
    OPENAI_API_KEY=$OPENAI_API_KEY \
    AI4BHARAT_API_KEY=$AI4BHARAT_API_KEY
RUN apt-get update && apt install build-essential --fix-missing -y
RUN wget --no-check-certificate https://dl.xpdfreader.com/xpdf-tools-linux-4.04.tar.gz &&  \
    tar -xvf xpdf-tools-linux-4.04.tar.gz && cp xpdf-tools-linux-4.04/bin64/pdftotext /usr/local/bin
RUN apt-get install ffmpeg -y
COPY requirements-prod.txt /root/
RUN pip3 install -r requirements-prod.txt
COPY gcp_credentials.json main.py query_with_gptindex.py cloud_storage.py query_with_langchain.py io_processing.py translator.py database_functions.py query_with_tfidf.py Titles.csv script.sh /root/
EXPOSE 8000
ENTRYPOINT ["bash","script.sh"]