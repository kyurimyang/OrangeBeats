@echo off
chcp 65001 >nul

echo.
echo  프론트엔드 다시 빌드 중...
echo.

cd /d "%~dp0orangebeats"
call npm run build
if %errorlevel% neq 0 (
    echo  빌드 실패!
    pause
    exit /b 1
)

echo.
echo  빌드 완료! start.bat 를 다시 실행하거나 서버를 재시작해주세요.
echo.
pause
