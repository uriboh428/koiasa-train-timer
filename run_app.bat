@echo off
chcp 65001 > nul
title 恋朝トレインタイマー (Streamlit)
echo ========================================================
echo   恋朝トレインタイマー (Streamlit Webダッシュボード)
echo ========================================================
echo.
echo ブラウザが自動的に開きます (http://localhost:8501)
echo 終了したいときは、このウィンドウを閉じるか Ctrl+C を押してください。
echo.

cd /d "%~dp0"
python -m streamlit run app.py

pause
