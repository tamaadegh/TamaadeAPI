#!/bin/bash

echo "🔄 Restarting Tamaade Django Application..."

# Stop all containers
echo "📦 Stopping containers..."
docker-compose down

# Remove old static files
echo "🗑️  Cleaning old static files..."
rm -rf staticfiles/*

# Collect static files
echo "📁 Collecting static files..."
docker-compose run --rm web python manage.py collectstatic --no-input --clear

# Start containers
echo "🚀 Starting containers..."
docker-compose up -d

echo "✅ Restart complete! Your application is now running."
echo "🌐 Admin interface: http://localhost:8000/admin/"
echo "📊 Dashboard: http://localhost:8000/dashboard/"
