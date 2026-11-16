@echo off
rem Bot ishlab turganda (python main.py), BOSHQA terminalda shuni ishga tushiring.
rem cloudflared o'rnatish (bir marta):  winget install Cloudflare.cloudflared
echo Pastda https://....trycloudflare.com manzili chiqadi. Uni nusxalang.
cloudflared tunnel --url http://localhost:8080
pause
