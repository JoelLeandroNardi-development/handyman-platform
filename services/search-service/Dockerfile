FROM python:3.11

WORKDIR /app

COPY ../../shared /shared
COPY ./app /app

RUN pip install fastapi uvicorn sqlalchemy asyncpg geoalchemy2 shapely

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
