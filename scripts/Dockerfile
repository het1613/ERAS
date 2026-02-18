FROM python:3.10-slim

WORKDIR /app

COPY shared/ /app/shared/

COPY scripts/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/simulate_vehicle_locations.py /app/simulate_vehicle_locations.py

CMD ["python", "simulate_vehicle_locations.py"]
