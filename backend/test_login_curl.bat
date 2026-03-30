@echo off
echo Testing login endpoint...
echo.

curl -X POST "http://localhost:8000/api/v1/auth/login" ^
  -H "accept: application/json" ^
  -H "Content-Type: application/x-www-form-urlencoded" ^
  -d "username=admin&password=bhiv2024"

echo.
echo.
echo Test complete!
pause
