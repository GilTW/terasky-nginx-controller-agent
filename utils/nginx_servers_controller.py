import logging
import os
import json
import anyio
import shutil
import requests
import utils.config as config
import utils.grpc_client as grpc_client
from pathlib import Path
from aws_utils import s3_helper


class NginxServersController:
    def __init__(self):
        self.nginx_servers_running = set()
        self.nginx_config_file_path = Path(config.HOST_TMP_FOLDER_MOUNT).joinpath("nginx.conf")
        self.nginx_config_backup_file_path = Path(config.HOST_TMP_FOLDER_MOUNT).joinpath("nginx.conf.backup")

    async def publish_configuration(self, publish_instructions, fallback_publish_instructions=None):
        try:
            await self.__download_new_config(publish_instructions["version"])

            async with anyio.create_task_group() as aio_task_group:
                for server_index in range(0, config.NGINX_SERVERS_COUNT):
                    nginx_server_container_name = f"nginx-server-{server_index}"

                    if nginx_server_container_name not in self.nginx_servers_running:
                        aio_task_group.start_soon(self.__start_nginx_server_container, nginx_server_container_name, publish_instructions)
                    else:
                        aio_task_group.start_soon(self.__update_nginx_server_container, nginx_server_container_name, publish_instructions)

            if self.nginx_config_backup_file_path.exists():
                os.remove(self.nginx_config_backup_file_path)

        except Exception as ex:
            await self.__roll_back(publish_instructions, fallback_publish_instructions)
            raise ex

    async def __download_new_config(self, version):
        if self.nginx_config_file_path.exists():
            shutil.copy2(self.nginx_config_file_path, self.nginx_config_backup_file_path)

        nginx_config_bucket_file_name = config.CONFIG_FILE_NAME_PATTERN.format(version=version)
        nginx_config_bucket_file_path = f"{config.CONFIG_VERSIONS_BUCKET_FOLDER}/{nginx_config_bucket_file_name}"
        new_config_file_content = s3_helper.get_file_content(config.DATA_BUCKET, nginx_config_bucket_file_path)

        if new_config_file_content is None:
            raise Exception("Config file couldn't be read.")

        self.nginx_config_file_path.write_text(new_config_file_content)

    async def __update_nginx_server_container(self, container_name, publish_instructions):
        if publish_instructions.get("restart_required", False):
            await anyio.run_process(f"docker stop {container_name}")
            self.nginx_servers_running.remove(container_name)
            await self.__start_nginx_server_container(container_name, publish_instructions)
        else:
            docker_nginx_reload_command = ["docker", "exec", container_name, "nginx", "-s", "reload"]
            await anyio.run_process(docker_nginx_reload_command)
            reloaded = False

            while not reloaded:
                if config.DEV_ENVIRONMENT:
                    config_server_response = await anyio.to_thread.run_sync(requests.get, f"http://localhost:{config.CONFIG_SERVER_PORT}/")
                else:
                    config_server_response = await anyio.to_thread.run_sync(requests.get, f"http://{container_name}:{config.CONFIG_SERVER_PORT}/")

                if config_server_response.status_code != 200:
                    raise Exception(f"Config server responded with code '{config_server_response.status_code}'. Error: {config_server_response.text}")
                elif config_server_response.text == publish_instructions["version"]:
                    break

                await anyio.sleep(0.1)

            logging.info(f"{container_name} reloaded successfully!")

        json_message = {
            "server_group": config.NGINX_SERVER_GROUP,
            "container_publish_result": "Success",
            "container_name": container_name
        }

        await grpc_client.notify(json.dumps(json_message))

    async def __start_nginx_server_container(self, container_name, publish_instructions):
        docker_run_command = ["docker", "run", "-d", "--rm", "--name", container_name, "--hostname", container_name,
                              "-v", f"{config.HOST_TMP_FOLDER}/nginx.conf:/etc/nginx/nginx.conf"]

        if config.DEV_ENVIRONMENT:
            docker_run_command.append("-p")
            docker_run_command.append(f"{config.CONFIG_SERVER_PORT}:{config.CONFIG_SERVER_PORT}")
        else:
            docker_run_command.append("--network")
            docker_run_command.append(config.NGINX_CONTROLLER_AGENT_DOCKER_NETWORK)

        for container_port in publish_instructions["exposed_ports"]:
            if container_port == "80":
                host_port = "8080"
            elif container_port == "443":
                host_port = "8443"
            else:
                host_port = container_port

            docker_run_command.append("-p")
            docker_run_command.append(f"{host_port}:{container_port}")

        docker_run_command.append(config.NGINX_SERVER_CONTAINER_IMAGE)
        await anyio.run_process(docker_run_command)
        self.nginx_servers_running.add(container_name)
        logging.info(f"{container_name} has started successfully!")

    async def __roll_back(self, latest_publish_instructions, fallback_publish_instructions):
        if self.nginx_config_backup_file_path.exists():
            os.remove(self.nginx_config_file_path)
            shutil.copy2(self.nginx_config_backup_file_path, self.nginx_config_file_path)
            os.remove(self.nginx_config_backup_file_path)

        if fallback_publish_instructions and latest_publish_instructions.get("restart_required", False):
            async with anyio.create_task_group() as aio_task_group:
                for server_index in range(0, config.NGINX_SERVERS_COUNT):
                    nginx_server_container_name = f"nginx-server-{server_index}"

                    if nginx_server_container_name not in self.nginx_servers_running:
                        aio_task_group.start_soon(self.__start_nginx_server_container, nginx_server_container_name, fallback_publish_instructions)
