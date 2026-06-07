#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Erreur: .venv introuvable. Lance: python -m venv .venv && pip install -r requirements.txt"
  exit 1
fi
source .venv/bin/activate
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "127.0.0.1")
echo "============================================"
echo "  Backend RPG Agent Company"
echo "  Local:   http://127.0.0.1:8080"
echo "  iPhone:  http://${IP}:8080/api/v1"
echo "  (iPhone et Mac sur le meme WiFi)"
echo "============================================"
exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
