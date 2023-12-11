FROM python:3.11-slim

RUN apt-get update && apt-get install -y

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1

COPY pyproject.toml poetry.lock ./

RUN pip install --upgrade pip && \
    pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-root

RUN mkdir /app/app
RUN mkdir /app/prompt

COPY ./app /app/app
COPY ./prompt /app/prompt

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

