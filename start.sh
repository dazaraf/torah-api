echo "Starting on port $PORT"
gunicorn torah-api:app --bind 0.0.0.0:$PORT
chmod +x start.sh
