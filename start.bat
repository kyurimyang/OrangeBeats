@echo off
chcp 65001 >nul

echo.
echo  OrangeBeats 개발 서버 시작 중...
echo.

:: Next.js 개발 서버를 별도 창으로 실행 (저장하면 자동 반영)
echo [1/2] 프론트엔드 개발 서버 시작 (새 창)...
start "OrangeBeats Frontend" cmd /k "cd /d "%~dp0orangebeats" && npm run dev"

:: 잠깐 대기 후 백엔드 실행
timeout /t 2 /nobreak >nul

echo [2/2] 백엔드 서버 시작 중...
echo.
echo   프론트엔드:  http://localhost:3000   ^<-- 여기로 접속 (저장하면 바로 반영)
echo   백엔드 API:  http://127.0.0.1:8000
echo.

cd /d "%~dp0"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
