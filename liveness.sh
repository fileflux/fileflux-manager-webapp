#!/bin/sh

if pgrep -f "python app.py" > /dev/null; then
  echo "Application is running"
  exit 0
else
  echo "Application is not running"
  exit 1
fi