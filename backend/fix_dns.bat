@echo off
echo ========================================
echo MongoDB Atlas DNS Fix Script
echo ========================================
echo.
echo This script will change your DNS servers to Google DNS
echo to fix MongoDB Atlas connectivity issues.
echo.
echo Current DNS: 192.168.0.1 (Router - CAUSING ISSUES)
echo New DNS: 8.8.8.8, 8.8.4.4 (Google DNS - RELIABLE)
echo.
pause

echo.
echo [INFO] Changing DNS servers for Ethernet connection...
netsh interface ip set dns "Ethernet" static 8.8.8.8
netsh interface ip add dns "Ethernet" 8.8.4.4 index=2

echo.
echo [INFO] Flushing DNS cache...
ipconfig /flushdns

echo.
echo [INFO] Testing new DNS configuration...
nslookup cluster0.acfgtzl.mongodb.net 8.8.8.8

echo.
echo [SUCCESS] DNS servers changed to Google DNS!
echo [INFO] Your MongoDB Atlas connection should now work.
echo.
echo To revert back to router DNS later, run:
echo netsh interface ip set dns "Ethernet" dhcp
echo.
pause
