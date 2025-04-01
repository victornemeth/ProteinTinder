# ~/annotate/Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies needed for mysqlclient and potentially other packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc \
       libmariadb-dev \
       netcat-openbsd \
       pkg-config \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code into the container
COPY . .

# Expose port 8000 for the Django dev server
EXPOSE 8000

# Command to run the application (will be often overridden by docker-compose or an entrypoint script)
# We will use an entrypoint script to handle migrations
# CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
