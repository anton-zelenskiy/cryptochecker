FROM python:3.7

RUN mkdir -p /home/project
WORKDIR /home/project
COPY requirements.txt /home/project
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH /home/project

COPY . /home/project
