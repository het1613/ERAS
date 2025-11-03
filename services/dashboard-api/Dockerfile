FROM python:3.10-slim

WORKDIR /app

# Copy shared utilities (will be copied from project root context)
COPY shared/ /app/shared/

# Copy and install dependencies
COPY services/dashboard-api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY services/dashboard-api/main.py /app/main.py

# Expose port
EXPOSE 8000

# Run the service
CMD ["python", "main.py"]

