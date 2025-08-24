# Use lightweight Python image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install gunicorn

# Copy project files
COPY . .

# Collect static files at build time
RUN python manage.py collectstatic --noinput

# Expose port for Gunicorn  
EXPOSE 8000

# Run Gunicorn server
CMD ["gunicorn", "payment_system.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
