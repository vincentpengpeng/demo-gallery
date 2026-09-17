@echo off
chcp 65001 >nul
echo ============================================
echo   真探 · 海外涉华信息智能核查平台
echo ============================================
echo.

REM 检查后端依赖
cd /d "%~dp0backend"
python -c "import fastapi, uvicorn, sqlalchemy" 2>nul
if errorlevel 1 (
    echo [安装] 后端依赖...
    python -m pip install -r requirements.txt
)

REM 检查前端依赖
cd /d "%~dp0frontend"
if not exist node_modules (
    echo [安装] 前端依赖...
    call npm install
)

echo.
echo [提示] 未配置 backend\.env 时，AI 能力将以演示模式运行。
echo        配置 .env（从 .env.example 复制并填入 ARK_API_KEY 等）后可启用真实能力。
echo.

REM 后台启动后端
cd /d "%~dp0backend"
start "真探-后端" cmd /k "python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

REM 启动前端
cd /d "%~dp0frontend"
echo [启动] 前端 http://localhost:5173
call npm run dev
