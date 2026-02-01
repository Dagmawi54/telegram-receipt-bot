FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Run web app
CMD ["gunicorn", "api:app", "--bind", "0.0.0.0:8080", "--workers", "2"]
