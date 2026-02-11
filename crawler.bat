@echo off
REM TMDB Movie Crawler
REM Usage: crawler.bat <api-key> [seed-file] [num-movies] [strategy] [output-dir]
REM
REM Parameters:
REM   api-key     : TMDB API key (required)
REM   seed-file   : Path to movie IDs file (default: data\movie_ids.jsonl)
REM   num-movies  : Max number of movies to crawl, 0 = all (default: 0)
REM   strategy    : Discovery strategy: genre|year|language|all (default: all)
REM   output-dir  : Output directory for movie JSON files (default: data\movies)
REM
REM Examples:
REM   crawler.bat YOUR_API_KEY
REM   crawler.bat YOUR_API_KEY data\movie_ids.jsonl 10000 all data\movies
REM   crawler.bat YOUR_API_KEY data\movie_ids.jsonl 0 genre data\movies

if "%~1"=="" (
    echo Error: API key is required.
    echo Usage: crawler.bat ^<api-key^> [seed-file] [num-movies] [strategy] [output-dir]
    exit /b 1
)

set "API_KEY=%~1"
set "SEED_FILE=%~2"
set "NUM_MOVIES=%~3"
set "STRATEGY=%~4"
set "OUTPUT_DIR=%~5"

if "%SEED_FILE%"=="" set "SEED_FILE=data\movie_ids.jsonl"
if "%NUM_MOVIES%"=="" set "NUM_MOVIES=0"
if "%STRATEGY%"=="" set "STRATEGY=all"
if "%OUTPUT_DIR%"=="" set "OUTPUT_DIR=data\movies"

set "SCRIPT_DIR=%~dp0"
set "CRAWLER_DIR=%SCRIPT_DIR%tmdb_crawler"
set "LOG_DIR=%SCRIPT_DIR%logs"
set "TMDB_API_KEY=%API_KEY%"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo === TMDB Movie Crawler ===
echo API Key    : %API_KEY:~0,8%...
echo Seed File  : %SEED_FILE%
echo Num Movies : %NUM_MOVIES%
echo Strategy   : %STRATEGY%
echo Output Dir : %OUTPUT_DIR%
echo.

REM Phase 1: Discover movie IDs
echo [Phase 1] Discovering movie IDs (strategy: %STRATEGY%)...
cd /d "%CRAWLER_DIR%"
scrapy crawl discover -a strategy=%STRATEGY% -s LOG_FILE="%LOG_DIR%\discover.log"

echo [Phase 1] Done.
echo.

REM Phase 2: Fetch movie details
echo [Phase 2] Fetching movie details...
set "CLOSE_SETTING="
if not "%NUM_MOVIES%"=="0" set "CLOSE_SETTING=-s CLOSESPIDER_ITEMCOUNT=%NUM_MOVIES%"

scrapy crawl details -a ids_file="%SCRIPT_DIR%%SEED_FILE%" -s MOVIES_DIR="%SCRIPT_DIR%%OUTPUT_DIR%" -s LOG_FILE="%LOG_DIR%\details.log" %CLOSE_SETTING%

echo.
echo === Crawl Complete ===
echo Output directory : %OUTPUT_DIR%
echo Logs             : %LOG_DIR%\
