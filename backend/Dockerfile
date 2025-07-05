# Use compatible base image
FROM python:3.7-slim

# Fix ENV format warning and logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies required for PyCrypto
RUN apt-get update && \
    apt-get install -y gcc libgmp-dev libffi-dev build-essential && \
    apt-get clean

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy your entire project code into container
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Run the app
CMD ["python", "run.py"]
