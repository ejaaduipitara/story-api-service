FROM continuumio/anaconda3:2023.03-1

WORKDIR /root
RUN apt-get update && apt-get install -y curl file
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH=$PATH:/root/.cargo/bin \
    OPENAI_API_KEY=$OPENAI_API_KEY \
    LOG_LEVEL=$LOG_LEVEL  \
    BHASHINI_ENDPOINT_URL=$BHASHINI_ENDPOINT_URL \
    BHASHINI_API_KEY=$BHASHINI_API_KEY \
    OCI_ENDPOINT_URL=$OCI_ENDPOINT_URL \
    OCI_REGION_NAME=$OCI_REGION_NAME \
    OCI_BUCKET_NAME=$OCI_BUCKET_NAME \
    OCI_SECRET_ACCESS_KEY=$OCI_SECRET_ACCESS_KEY \
    OCI_ACCESS_KEY_ID=$OCI_ACCESS_KEY_ID \
    SERVICE_ENVIRONMENT=$SERVICE_ENVIRONMENT \
    TELEMETRY_ENDPOINT_URL=$TELEMETRY_ENDPOINT_URL
RUN apt-get update && apt install build-essential --fix-missing -y
RUN wget --no-check-certificate https://dl.xpdfreader.com/xpdf-tools-linux-4.04.tar.gz &&  \
    tar -xvf xpdf-tools-linux-4.04.tar.gz && cp xpdf-tools-linux-4.04/bin64/pdftotext /usr/local/bin
RUN apt-get install ffmpeg -y
COPY requirements-prod.txt /root/
RUN pip3 install -r requirements-prod.txt
COPY main.py cloud_storage_oci.py query_with_langchain.py io_processing.py translator.py logger.py script.sh utils.py telemetry_logger.py /root/
EXPOSE 8000
ENTRYPOINT ["bash","script.sh"]