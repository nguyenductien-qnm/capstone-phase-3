# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Generated-compatible protobuf module for pb/shopping_copilot.proto.
# Kept in source because the service image does not run grpc_tools at startup.

from google.protobuf import descriptor_pb2 as _descriptor_pb2
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

_sym_db = _symbol_database.Default()


def _add_field(message, name, number, field_type, label=1, type_name=None, deprecated=False):
    field = message.field.add()
    field.name = name
    field.number = number
    field.label = label
    field.type = field_type
    if type_name:
        field.type_name = type_name
    if deprecated:
        field.options.deprecated = True


_file_proto = _descriptor_pb2.FileDescriptorProto()
_file_proto.name = "shopping_copilot.proto"
_file_proto.package = "oteldemo"
_file_proto.syntax = "proto3"
_file_proto.options.go_package = "genproto/oteldemo"

_chat_request = _file_proto.message_type.add()
_chat_request.name = "ChatWithCopilotRequest"
_add_field(_chat_request, "user_id", 1, 9)
_add_field(_chat_request, "question", 2, 9)
_add_field(_chat_request, "chat_history", 3, 9, label=3, deprecated=True)
_add_field(_chat_request, "session_id", 4, 9)
_add_field(_chat_request, "confirmation_token", 5, 9)

_pending_confirmation = _file_proto.message_type.add()
_pending_confirmation.name = "PendingConfirmation"
_add_field(_pending_confirmation, "tool_name", 1, 9)
_add_field(_pending_confirmation, "arguments_json", 2, 9)
_add_field(_pending_confirmation, "human_prompt", 3, 9)
_add_field(_pending_confirmation, "confirmation_token", 4, 9)
_add_field(_pending_confirmation, "expires_at_unix", 5, 3)

_tool_call_record = _file_proto.message_type.add()
_tool_call_record.name = "ToolCallRecord"
_add_field(_tool_call_record, "tool_name", 1, 9)
_add_field(_tool_call_record, "arguments_json", 2, 9)
_add_field(_tool_call_record, "succeeded", 3, 8)
_add_field(_tool_call_record, "started_at_unix", 4, 3)
_add_field(_tool_call_record, "duration_ms", 5, 3)

_citation = _file_proto.message_type.add()
_citation.name = "Citation"
_add_field(_citation, "review_id", 1, 9)
_add_field(_citation, "snippet", 2, 9)
_add_field(_citation, "score", 3, 9)

_chat_response = _file_proto.message_type.add()
_chat_response.name = "ChatWithCopilotResponse"
_add_field(_chat_response, "response", 1, 9)
_add_field(_chat_response, "pending_confirmation", 2, 11, type_name=".oteldemo.PendingConfirmation")
_add_field(_chat_response, "actions_taken", 3, 11, label=3, type_name=".oteldemo.ToolCallRecord")
_add_field(_chat_response, "degraded", 4, 8)
_add_field(_chat_response, "trace_id", 5, 9)
_add_field(_chat_response, "citations", 6, 11, label=3, type_name=".oteldemo.Citation")

_service = _file_proto.service.add()
_service.name = "ShoppingCopilotService"
_method = _service.method.add()
_method.name = "ChatWithCopilot"
_method.input_type = ".oteldemo.ChatWithCopilotRequest"
_method.output_type = ".oteldemo.ChatWithCopilotResponse"

DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(_file_proto.SerializeToString())

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, "shopping_copilot_pb2", _globals)
