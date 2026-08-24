@echo off
echo Starting AgriMate Backend...
start cmd /k "cd app\backend && uvicorn main:app --host 127.0.0.1 --port 8000"

echo Starting AgriMate Frontend...
cd app\frontend
npm install
npm run dev
