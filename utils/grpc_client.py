import grpc
import logging
import utils.config as config
import grpc_utils.nginx_controller_server_pb2 as pb2
import grpc_utils.nginx_controller_server_pb2_grpc as pb2_grpc

logger = logging.getLogger("GRPC-Client")


async def notify(message):
    async with grpc.aio.insecure_channel(f'{config.CONTROLLER_GRPC_ADDRESS}:{config.CONTROLLER_GRPC_PORT}') as channel:
        agent_notify_stub = pb2_grpc.AgentNotifyStub(channel)

        # Make gRPC requests
        message = pb2.Message(message=message)
        response = await agent_notify_stub.notify(message)
        logger.debug(f'Message received: {response.received}')
