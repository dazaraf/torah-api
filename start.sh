echo "Starting on port $PORT"
#!/bin/bash
gunicorn torah-api:app --bind 0.0.0.0:$PORT --timeout 120 --workers 2 --threads 4
chmod +x start.sh
