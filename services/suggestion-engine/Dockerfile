FROM python:3.10-slim

WORKDIR /app

# Copy shared utilities (will be copied from project root context)
COPY shared/ /app/shared/

# Copy and install dependencies
COPY services/suggestion-engine/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY services/suggestion-engine/main.py /app/main.py

# Run the service
CMD ["python", "main.py"]

