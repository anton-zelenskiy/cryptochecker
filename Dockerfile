FROM python:3.10.4-alpine

RUN mkdir -p /home/project
WORKDIR /home/project
COPY conf/requirements.txt /home/project
COPY conf/constraints.txt /home/project
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt

ENV PYTHONPATH /home

COPY . .
