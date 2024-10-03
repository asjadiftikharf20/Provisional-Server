# Base image
FROM python:3.12.6-slim

# Set working directory
WORKDIR /app

# Copy requirements file (if you have one) or install packages directly
COPY requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# If you don't use a requirements.txt file, you can directly install the package like this:
# RUN pip install azure-iot-device

# Copy all source code into the container
COPY . /app

# Expose the port the server listens on
EXPOSE 8080

# Command to run the server
CMD ["python", "http_tcp_server.py"]
