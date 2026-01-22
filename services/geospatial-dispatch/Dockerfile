FROM python:3.10-slim

WORKDIR /app

# Copy shared utilities (will be copied from project root context)
COPY shared/ /app/shared/

# Copy and install dependencies
COPY services/geospatial-dispatch/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY services/geospatial-dispatch/main.py /app/main.py
COPY services/geospatial-dispatch/optimization.py /app/optimization.py

# Expose port
EXPOSE 8002

# Run the service
CMD ["python", "main.py"]

