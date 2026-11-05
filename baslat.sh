#!/bin/zsh
# Paneli başlatır: ./baslat.sh
cd "$(dirname "$0")"
if [ ! -x .venv/bin/streamlit ]; then
  echo "Kurulum yapılıyor..."
  /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12 -m venv .venv
  ./.venv/bin/pip install -r requirements.txt
fi
exec ./.venv/bin/streamlit run app.py
