@echo off
echo === Build PDF-TOC-Translator.exe ===
pip install --upgrade pip
pip install -r requirements.txt

pyinstaller --noconfirm --onefile --windowed ^
  --name Dich-Bookmark-PDF ^
  --hidden-import pypdf ^
  --hidden-import google.generativeai ^
  --collect-all google.generativeai ^
  app.py

echo.
echo === Xong! File exe nam trong dist\PDF-TOC-Translator.exe ===
pause