# Use Python 3.9 as the base image
FROM python:3.12.6-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any required Python packages (if any exist in a requirements.txt file)
# If your project doesn't need external libraries, you can remove this
# RUN pip install --no-cache-dir -r requirements.txt

# Expose the port (replace with your desired port)
EXPOSE 8080

# Command to run your server.py when the container starts
CMD ["python3", "server.py"]
