@echo off
REM Wrapper for Windows Task Scheduler: refresh arXiv dashboard data daily.
cd /d "E:\claude_github\arxiv-dash"
"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe" daily_update.py
