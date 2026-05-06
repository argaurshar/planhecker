@echo off
cd /d "%~dp0"
echo.
echo  PlanCheck Lite - starting local server
echo  ----------------------------------------
echo.
echo  When you see "Local URL: http://localhost:8501",
echo  your browser should open automatically.
echo  To stop the app, press Ctrl+C in this window.
echo.
venv\Scripts\streamlit.exe run app.py
pause
