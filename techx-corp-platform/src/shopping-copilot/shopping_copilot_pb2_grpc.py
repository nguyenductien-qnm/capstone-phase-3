# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import grpc

import shopping_copilot_pb2 as shopping__copilot__pb2


class ShoppingCopilotServiceStub(object):
    def __init__(self, channel):
        self.ChatWithCopilot = channel.unary_unary(
            "/oteldemo.ShoppingCopilotService/ChatWithCopilot",
            request_serializer=shopping__copilot__pb2.ChatWithCopilotRequest.SerializeToString,
            response_deserializer=shopping__copilot__pb2.ChatWithCopilotResponse.FromString,
        )


class ShoppingCopilotServiceServicer(object):
    def ChatWithCopilot(self, request, context):
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("Method not implemented!")
        raise NotImplementedError("Method not implemented!")


def add_ShoppingCopilotServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
        "ChatWithCopilot": grpc.unary_unary_rpc_method_handler(
            servicer.ChatWithCopilot,
            request_deserializer=shopping__copilot__pb2.ChatWithCopilotRequest.FromString,
            response_serializer=shopping__copilot__pb2.ChatWithCopilotResponse.SerializeToString,
        ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
        "oteldemo.ShoppingCopilotService", rpc_method_handlers
    )
    server.add_generic_rpc_handlers((generic_handler,))


class ShoppingCopilotService(object):
    @staticmethod
    def ChatWithCopilot(
        request,
        target,
        options=(),
        channel_credentials=None,
        call_credentials=None,
        insecure=False,
        compression=None,
        wait_for_ready=None,
        timeout=None,
        metadata=None,
    ):
        return grpc.experimental.unary_unary(
            request,
            target,
            "/oteldemo.ShoppingCopilotService/ChatWithCopilot",
            shopping__copilot__pb2.ChatWithCopilotRequest.SerializeToString,
            shopping__copilot__pb2.ChatWithCopilotResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
        )
