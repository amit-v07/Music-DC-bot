@echo off
cd music_web_app
echo Installing dependencies...
pip install -r requirements.txt
echo.
echo Starting Music Web App on Port 5005...
echo Access at: http://localhost:5005
python app.py
pause
