#!/bin/bash
gunicorn torah_api:app --bind 0.0.0.0:$PORT