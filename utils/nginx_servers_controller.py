import os
import json
import anyio
import shutil
import logging
import requests
import utils.config as config
import utils.grpc_client as grpc_client
from pathlib import Path
from datetime import datetime
from aws_utils import s3_helper


class NginxServersController:
    def __init__(self):
        self.nginx_servers_running = set()
        self.nginx_config_file_path = Path(config.HOST_TMP_FOLDER_MOUNT).joinpath("nginx.conf")
        self.nginx_config_backup_file_path = Path(config.HOST_TMP_FOLDER_MOUNT).joinpath("nginx.conf.backup")

    async def publish_configuration(self, publish_instructions, fallback_publish_instructions=None):
        try:
            await self.__download_new_config(publish_instructions["version"])

            if publish_instructions.get("restart_required", False) and len(self.nginx_servers_running) > 0:
                logging.info(f"Restart required!")

            start_time = await anyio.current_time()

            async with anyio.create_task_group() as aio_task_group:
                async with anyio.move_on_after(config.PUBLISH_TIMEOUT_SECONDS) as timeout_scope:
                    for server_index in range(0, config.NGINX_SERVERS_COUNT):
                        nginx_server_container_name = f"nginx-server-{server_index}"

                        if nginx_server_container_name not in self.nginx_servers_running:
                            aio_task_group.start_soon(self.__start_nginx_server_container, nginx_server_container_name, publish_instructions)
                        else:
                            aio_task_group.start_soon(self.__update_nginx_server_container, nginx_server_container_name, publish_instructions)

                if timeout_scope.cancel_called:
                    raise Exception("Publish timeout has reached!")

            end_time = await anyio.current_time()
            time_took_sec = end_time - start_time
            logging.info(f"Publishing version {publish_instructions['version']} took {time_took_sec} seconds.")

            if datetime.now().timestamp() - publish_instructions["timestamp"] < config.PUBLISH_TIMEOUT_SECONDS:
                await self.__notify_controller(time_took_sec)

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
        start_time = await anyio.current_time()

        if publish_instructions.get("restart_required", False):
            self.nginx_servers_running.remove(container_name)
            await self.__start_nginx_server_container(container_name, publish_instructions)
        else:
            logging.info(f"Reloading {container_name}")
            docker_nginx_reload_command = ["docker", "exec", container_name, "nginx", "-s", "reload"]
            await self.__docker_command_handler(docker_nginx_reload_command)
            logging.info(f"{container_name} reloaded.")
            await self.__check_nginx_server(container_name, version=publish_instructions["version"])

        end_time = await anyio.current_time()
        time_took_sec = end_time - start_time
        logging.info(f"Updating {container_name} took {time_took_sec} seconds.")

    async def __start_nginx_server_container(self, container_name, publish_instructions):
        docker_stop_command = ["docker", "stop", container_name]
        logging.info(f"Stopping {container_name}...")
        await self.__docker_command_handler(docker_stop_command, throw_on_error=False)

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
        logging.info(f"Starting {container_name}...")
        await self.__docker_command_handler(docker_run_command)
        logging.info(f"{container_name} has started.")
        await self.__check_nginx_server(container_name, version=publish_instructions["version"])
        self.nginx_servers_running.add(container_name)

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

    @staticmethod
    async def __docker_command_handler(docker_command, throw_on_error=True):
        logging.debug(f"Running command '{' '.join(docker_command)}'")
        response = await anyio.run_process(docker_command, check=throw_on_error)
        logging.debug(f"Response -> {response}")

        return response

    @staticmethod
    async def __check_nginx_server(container_name, version):
        server_updated = False

        if config.DEV_ENVIRONMENT:
            config_endpoint = f"http://localhost:{config.CONFIG_SERVER_PORT}/"
        else:
            config_endpoint = f"http://{container_name}:{config.CONFIG_SERVER_PORT}/"

        logging.info(f"Checking Nginx server config endpoint In '{config_endpoint}'")
        config_server_response = None
        await anyio.sleep(1)

        async with anyio.move_on_after(9) as timeout_scope:
            while not server_updated:
                try:
                    config_server_response = await anyio.to_thread.run_sync(requests.get, config_endpoint)
                except Exception:
                    pass

                if config_server_response:
                    if config_server_response.status_code != 200:
                        raise Exception(
                            f"{container_name} config server responded with code '{config_server_response.status_code}'. Error: {config_server_response.text}")
                    elif config_server_response.text == version:
                        logging.info(f"{container_name} is up with version {version}!")
                        server_updated = True

                await anyio.sleep(0.1)

        if timeout_scope.cancel_called:
            raise Exception("Nginx Server has not updated within the timeout period")

    @staticmethod
    async def __notify_controller(time_took_seconds):
        json_message = {
            "server_group": config.NGINX_SERVER_GROUP,
            "containers_publish_result": "Success",
            "containers_count": config.NGINX_SERVERS_COUNT,
            "time_took_seconds": time_took_seconds
        }

        await grpc_client.notify(json.dumps(json_message))
