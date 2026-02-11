@echo off
echo Starting Debug Mode...
call venv\Scripts\activate
python -m app.main > debug.log 2>&1
echo Application stopped. Check debug.log for details.
pause
