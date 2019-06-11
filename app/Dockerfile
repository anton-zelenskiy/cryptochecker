FROM python:3.7

RUN mkdir -p /home/project/app
WORKDIR /home/project/app
COPY requirements.txt /home/project/app
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH /home/project/app

COPY . /home/project/app
