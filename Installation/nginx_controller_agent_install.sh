#!/bin/bash

# Exit On Error
set -e

# Source Environment Variables
echo "Step 1 - Sourcing Config Environment Variables"
echo "-----------------------------------------------------------------------------------------------------------"
ENV_CONFIG_FILE="./config.env"
echo "# Reading Environmnet Variables From '$ENV_CONFIG_FILE'"
source "$ENV_CONFIG_FILE"
echo "# Done!"
echo ""

# Run Docker Login Command
echo "Step 2 - Docker Repository Login"
echo "-----------------------------------------------------------------------------------------------------------"
echo "# Logging To Docker Repository"
echo "- Command: $DOCKER_LOGIN_COMMAND"
eval "$DOCKER_LOGIN_COMMAND"
echo "# Done!"
echo ""

# Pull Nginx Server Container Image
echo "Step 3 - Pull Nginx Server Container"
echo "-----------------------------------------------------------------------------------------------------------"
echo "# Pulling Nginx Server Image From '$NGINX_SERVER_CONTAINER_IMAGE'"
echo "- Command: docker pull $NGINX_SERVER_CONTAINER_IMAGE"
sudo docker pull $NGINX_SERVER_CONTAINER_IMAGE
echo "# Done"
echo ""

# Pull Nginx Controller Agent Container Image
echo "Step 4 - Pull Nginx Controll Agent Container"
echo "-----------------------------------------------------------------------------------------------------------"
echo "# Pulling Nginx Server Image From '$NGINX_CONTROLLER_AGENT_CONTAINER_IMAGE'"
echo "- Command: docker pull $NGINX_CONTROLLER_AGENT_CONTAINER_IMAGE"
sudo docker pull $NGINX_CONTROLLER_AGENT_CONTAINER_IMAGE
echo "# Done"
echo ""

# Create Agent Docker Network
echo "Step 5 - Creating Agent Controller Systemd Service"
echo "-----------------------------------------------------------------------------------------------------------"

if docker network list | grep -q "$NGINX_CONTROLLER_AGENT_DOCKER_NETWORK"; then
	echo "# Netowrk '$NGINX_CONTROLLER_AGENT_DOCKER_NETWORK' Exists.";
else
	echo "# Creating Docker Network '$NGINX_CONTROLLER_AGENT_DOCKER_NETWORK'";
	sudo docker network create "$NGINX_CONTROLLER_AGENT_DOCKER_NETWORK";
	echo "# Done";
fi

echo ""

echo "Step 6 - Creating Agent Controller Systemd Service"
echo "-----------------------------------------------------------------------------------------------------------"
# Create Nginx Controller Agent Service File
SYSTEMD_FOLDER="/etc/systemd/system"
SYSTEMD_SERVICE_FOLDER="$SYSTEMD_FOLDER/nginx-controller-agent"
AGENT_CONTAINER_NAME="nginx-controller-agent"
NGINX_CONTROLLER_SERVICE_FILE_NAME="nginx-controller-agent.service"
NGINX_CONTROLLER_SERVICE_FILE_CONTENT="[Unit]
Description=Nginx Controller Agent Container
After=docker.service
Requires=docker.service

[Service]
TimeoutStartSec=0
TimeoutStopSec=5
Restart=always
ExecStartPre=$DOCKER_LOGIN_COMMAND
ExecStartPre=-/usr/bin/docker container stop $AGENT_CONTAINER_NAME
ExecStartPre=-/usr/bin/docker container rm $AGENT_CONTAINER_NAME
ExecStartPre=sudo /usr/bin/docker pull $NGINX_SERVER_CONTAINER_IMAGE
ExecStartPre=sudo /usr/bin/docker pull $NGINX_CONTROLLER_AGENT_CONTAINER_IMAGE
ExecStart=/usr/bin/docker run --rm --name $AGENT_CONTAINER_NAME --mount type=bind,source="$HOST_TMP_FOLDER",target="$HOST_TMP_FOLDER_MOUNT" \
--mount type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock --env-file "$SYSTEMD_SERVICE_FOLDER/$ENV_CONFIG_FILE" \
--network $NGINX_CONTROLLER_AGENT_DOCKER_NETWORK $NGINX_CONTROLLER_AGENT_CONTAINER_IMAGE
ExecStop=/usr/bin/docker stop $AGENT_CONTAINER_NAME

[Install]
WantedBy=multi-user.target"

echo "# Creating Systemd Service '$NGINX_CONTROLLER_SERVICE_FILE_NAME'"
sudo mkdir -p "$SYSTEMD_SERVICE_FOLDER"
sudo cp "./$ENV_CONFIG_FILE" "$SYSTEMD_SERVICE_FOLDER/$ENV_CONFIG_FILE"
sudo sh -c "echo '$NGINX_CONTROLLER_SERVICE_FILE_CONTENT' > '$SYSTEMD_FOLDER/$NGINX_CONTROLLER_SERVICE_FILE_NAME'"
sudo systemctl daemon-reload
sudo systemctl restart "${NGINX_CONTROLLER_SERVICE_FILE_NAME%.service}"
sudo systemctl enable "${NGINX_CONTROLLER_SERVICE_FILE_NAME%.service}"
echo "# Done"
echo ""