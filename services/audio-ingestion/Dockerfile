FROM python:3.11-slim

WORKDIR /app

# Copy shared modules first
COPY ../../shared /app/shared

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY . .

EXPOSE 8001

CMD ["python", "main.py"]

