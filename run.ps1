$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
python -m uvicorn app.main:app --reload
