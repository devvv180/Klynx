@echo off
REM Run LLM-based event filtering for Client Risk Dashboard
REM This will create llm_filtered_relevant_events.jsonl with only relevant events

echo ========================================
echo LLM-Based Event Filtering
echo ========================================
echo.

REM Check if GROQ_API_KEY is set
if "%GROQ_API_KEY%"=="" (
    echo ERROR: GROQ_API_KEY environment variable not set
    echo.
    echo Please set it with:
    echo   set GROQ_API_KEY=your-key-here
    echo.
    echo Or add it to your system environment variables
    pause
    exit /b 1
)

echo Using Groq API for LLM filtering...
echo This will take 2-3 minutes for 188 events
echo.

python llm_relevance_filter.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCCESS! Filtered events saved to:
    echo   data/llm_filtered_relevant_events.jsonl
    echo ========================================
    echo.
    echo The dashboard will now automatically use these filtered events.
) else (
    echo.
    echo ========================================
    echo ERROR: Filtering failed
    echo ========================================
    echo.
    echo Check the error messages above for details.
)

pause
