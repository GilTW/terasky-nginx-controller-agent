import os

DEV_ENVIRONMENT = os.environ.get("DEV_ENVIRONMENT", False)
NGINX_CONTROLLER_AGENT_DOCKER_NETWORK = None

if not DEV_ENVIRONMENT:
    NGINX_CONTROLLER_AGENT_DOCKER_NETWORK = os.environ.get("NGINX_CONTROLLER_AGENT_DOCKER_NETWORK", None)

NGINX_SERVER_CONTAINER_IMAGE = os.environ["NGINX_SERVER_CONTAINER_IMAGE"]
CONFIG_SERVER_PORT = os.environ["CONFIG_SERVER_PORT"]
NGINX_SERVER_GROUP = os.environ["NGINX_SERVER_GROUP"]
NGINX_SERVERS_COUNT = int(os.environ["NGINX_SERVERS_COUNT"])
CONTROLLER_GRPC_PORT = os.environ["CONTROLLER_GRPC_PORT"]
CONTROLLER_GRPC_ADDRESS = os.environ["CONTROLLER_GRPC_ADDRESS"]
DATA_BUCKET = os.environ["DATA_BUCKET"]
CONFIG_VERSIONS_BUCKET_FOLDER = os.environ["CONFIG_VERSIONS_BUCKET_FOLDER"]
RUNNING_VERSIONS_BUCKET_FOLDER = os.environ["RUNNING_VERSIONS_BUCKET_FOLDER"]
CONFIG_FILE_NAME_PATTERN = os.environ["CONFIG_FILE_NAME_PATTERN"]
GROUP_RUNNING_VERSION_FILE_NAME_PATTERN = os.environ["GROUP_RUNNING_VERSION_FILE_NAME_PATTERN"]
BUCKET_POLLING_SECONDS_INTERVAL = int(os.environ["BUCKET_POLLING_SECONDS_INTERVAL"])
HOST_TMP_FOLDER = os.environ["HOST_TMP_FOLDER"]
HOST_TMP_FOLDER_MOUNT = os.environ["HOST_TMP_FOLDER_MOUNT"]
PUBLISH_TIMEOUT_SECONDS = int(os.environ["PUBLISH_TIMEOUT_SECONDS"])
