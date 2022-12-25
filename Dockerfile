FROM lambci/lambda:build-python3.8

ENV VIRTUAL_ENV=venv
ENV PATH $VIRTUAL_ENV/bin:$PATH
RUN python -m venv $VIRTUAL_ENV

RUN pip install --upgrade pip
Run yum install -y poppler-utils

COPY requirements.txt .
RUN pip install -r requirements.txt
WORKDIR /var/task/venv/lib/python3.8/site-packages

COPY hebrew_vocabulary_list.txt .
COPY lambda_function.py .

RUN zip -9qr upload-to-s3.zip .
RUN echo "upload-to-s3.zip created"
ENTRYPOINT ["bash"]
