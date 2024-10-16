# Base image
FROM python:3.12.6-slim

# Set working directory
WORKDIR /app

# Copy requirements file (if you have one) or install packages directly
COPY requirements.txt /app/requirements.txt

# Install dependencies and system packages (including Redis and supervisord)
RUN apt-get update
RUN apt-get install -y redis supervisor
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy all source code into the container
COPY . /app

# Copy supervisor configuration file
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose the port the server listens on
EXPOSE 8080

# Start supervisord to manage Redis and the Python server
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
