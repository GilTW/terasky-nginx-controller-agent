import anyio
import json
import logging
import hashlib
import utils.config as config
from aws_utils import s3_helper
from utils.nginx_servers_controller import NginxServersController

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
broken_versions_sigs = set()


async def main():
    logging.info("Starting Nginx Controller Agent")
    nginx_servers_controller = NginxServersController()
    current_version_publish_instructions = None
    current_version_publish_instructions_sig = None
    running_version_bucket_file = f"{config.RUNNING_VERSIONS_BUCKET_FOLDER}/" \
                                  f"{config.GROUP_RUNNING_VERSION_FILE_NAME_PATTERN.format(group=config.NGINX_SERVER_GROUP)}"

    while True:
        running_version_bucket_file_content = s3_helper.get_file_content(config.DATA_BUCKET, running_version_bucket_file)

        if running_version_bucket_file_content is not None:
            new_version_publish_instructions_sig = hashlib.sha256(running_version_bucket_file_content.encode()).hexdigest()

            if new_version_publish_instructions_sig != current_version_publish_instructions_sig and \
                    new_version_publish_instructions_sig not in broken_versions_sigs:
                try:
                    new_version_publish_instructions = json.loads(running_version_bucket_file_content)
                    version = new_version_publish_instructions["version"]

                    if current_version_publish_instructions_sig is None:
                        logging.info(f"Initial Startup - Running Nginx servers with version '{version}'")
                    else:
                        logging.info(f"New Version Publish - Publishing Nginx servers with version '{version}'")

                    await nginx_servers_controller.publish_configuration(new_version_publish_instructions,
                                                                         fallback_publish_instructions=current_version_publish_instructions)
                    current_version_publish_instructions_sig = new_version_publish_instructions_sig
                except Exception as ex:
                    broken_versions_sigs.add(new_version_publish_instructions_sig)
                    logging.error(ex)

        await anyio.sleep(config.BUCKET_POLLING_SECONDS_INTERVAL)


if __name__ == "__main__":
    anyio.run(main)
