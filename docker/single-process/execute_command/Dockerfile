FROM python:3.10-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

# Create a virtual environment for commands/python/chat_gpt app
RUN python -m venv /app/commands/python/chat_gpt/venv \
    && . /app/commands/python/chat_gpt/venv/bin/activate \
    && pip install --no-cache-dir -r /app/commands/python/chat_gpt/requirements.txt

EXPOSE 3535

ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=3535

CMD ["gunicorn", "-b", "0.0.0.0:3535", "app:app"]
