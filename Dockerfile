# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dashboard folder contents into /app
COPY dashboard/ /app

# Install dependencies
COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

# Environment variables
ENV MQTT_SERVER=94.182.137.200
ENV MQTT_PORT=1883

# Run app.py
CMD ["python", "app.py"]
