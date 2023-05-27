@echo off

setlocal

aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin 878291911462.dkr.ecr.eu-central-1.amazonaws.com
if not %errorlevel% equ 0 exit /b %errorlevel%

cd ..
docker build -f ./nginx-controller-agent/Dockerfile -t nginx-controller-agent .
if not %errorlevel% equ 0 exit /b %errorlevel%

docker tag nginx-controller-agent:latest 878291911462.dkr.ecr.eu-central-1.amazonaws.com/nginx-controller-agent:latest
if not %errorlevel% equ 0 exit /b %errorlevel%

docker push 878291911462.dkr.ecr.eu-central-1.amazonaws.com/nginx-controller-agent:latest
if not %errorlevel% equ 0 exit /b %errorlevel%

endlocal