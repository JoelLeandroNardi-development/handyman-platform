ARG PYTHON_VERSION=3.14.3
FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

COPY services/search-service/requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel \
	&& python -m pip install --no-cache-dir -r /app/requirements.txt

COPY shared /app/shared
RUN python -m pip install --no-cache-dir -e /app/shared

COPY services/search-service/app /app/app

ENV PYTHONPATH=/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
