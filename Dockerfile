FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY models/ ./models/

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 5001

# Run the application
CMD ["python", "app.py"]
