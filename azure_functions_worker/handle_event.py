# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import asyncio
import logging
import os
import sys

from datetime import datetime
from enum import Enum
from typing import List, Optional

from .functions import index_functions
from .http_v2 import (
    HttpServerInitError,
    HttpV2Registry,
    http_coordinator,
    initialize_http_server,
    sync_http_request,
)
from .version import VERSION

from .bindings.meta import load_binding_registry
from .utils.app_setting_state import get_python_appsetting_state
from .utils.constants import (FUNCTION_DATA_CACHE,
                              RAW_HTTP_BODY_BYTES,
                              TYPED_DATA_COLLECTION,
                              RPC_HTTP_BODY_ONLY,
                              WORKER_STATUS,
                              RPC_HTTP_TRIGGER_METADATA_REMOVED,
                              SHARED_MEMORY_DATA_TRANSFER,
                              TRUE, TRACEPARENT, TRACESTATE,
                              PYTHON_ENABLE_OPENTELEMETRY,
                              PYTHON_ENABLE_OPENTELEMETRY_DEFAULT,
                              WORKER_OPEN_TELEMETRY_ENABLED,
                              PYTHON_ENABLE_INIT_INDEXING,
                              HTTP_URI,
                              REQUIRES_ROUTE_PARAMETERS,
                              PYTHON_SCRIPT_FILE_NAME,
                              PYTHON_SCRIPT_FILE_NAME_DEFAULT,
                              METADATA_PROPERTIES_WORKER_INDEXED,
                              PYTHON_ENABLE_DEBUG_LOGGING)
from .utils.env_state import get_app_setting, is_envvar_true

metadata_result: str = ""
metadata_exception: Optional[Exception] = None

class StringifyEnum(Enum):
    """This class output name of enum object when printed as string."""
    def __str__(self):
        return str(self.name)

class Status(StringifyEnum):
    SUCCESS = 200
    ERROR = 400


class WorkerResponse:
    def __init__(self, name: Optional[str] = None, status: Optional[Status] = None, result: Optional[dict] = None, exception: Optional[dict] = None):
        # WorkerResponse(name: "init response", status: ENUM.success, result: {"capabilities": "", <varies by request type>}, exception: {status_code: "", type: "", message: ""})
        self._name = name
        self._status = status
        self._result = result
        self._exception = exception


# Protos will be the retry / binding / metadata protos object that we populate and return
async def worker_init_request(self, request, protos):
    worker_init_request = request.worker_init_request
    host_capabilities = worker_init_request.capabilities
    if FUNCTION_DATA_CACHE in host_capabilities:
        val = host_capabilities[FUNCTION_DATA_CACHE]
        self._function_data_cache_enabled = val == TRUE

    capabilities = {
        RAW_HTTP_BODY_BYTES: TRUE,
        TYPED_DATA_COLLECTION: TRUE,
        RPC_HTTP_BODY_ONLY: TRUE,
        WORKER_STATUS: TRUE,
        RPC_HTTP_TRIGGER_METADATA_REMOVED: TRUE,
        SHARED_MEMORY_DATA_TRANSFER: TRUE,
    }
    if get_app_setting(setting=PYTHON_ENABLE_OPENTELEMETRY,
                       default_value=PYTHON_ENABLE_OPENTELEMETRY_DEFAULT):
        # Todo: Refactor open telemetry setup into separate file
        self.initialize_azure_monitor()

        if self._azure_monitor_available:
            capabilities[WORKER_OPEN_TELEMETRY_ENABLED] = TRUE


    # loading bindings registry and saving results to a static
    # dictionary which will be later used in the invocation request
    load_binding_registry()

    # TODO: load_function_metadata
    # global MR & ME & result
    # result = asyncio.createTask(indexing) -- MR / ME set in indexing
    try:
        result = asyncio.create_task(load_function_metadata(worker_init_request.function_app_directory,
                                                            caller_info="worker_init_request"))
        if get_app_setting(setting=PYTHON_ENABLE_INIT_INDEXING): # PYTHON_ENABLE_HTTP_STREAMING
            capabilities[HTTP_URI] = \
                initialize_http_server(self._host)
            capabilities[REQUIRES_ROUTE_PARAMETERS] = TRUE
    except HttpServerInitError:
        raise
    except Exception as ex:
        # Todo: Do we need to save metadata_exception here?
        global metadata_exception
        metadata_exception = ex
        WorkerResponse(name="worker_init_request",
                       status=Status.ERROR,
                       result={"capabilities": capabilities},
                       exception={"status_code": ex.status, "type": type(ex), "message": ex})

    return WorkerResponse(name="worker_init_request",
                          status=Status.SUCCESS,
                          result={"capabilities": capabilities},
                          exception={"status_code": 200, "type": None, "message": None})


#handle__worker_status_request can be done in the proxy worker

async def functions_metadata_request(self, request):
    metadata_request = request.functions_metadata_request
    function_app_directory = metadata_request.function_app_directory

    # Todo: just await metadata result and exception
    # await result
    # If ME return exception, else return MR
    if not is_envvar_true(PYTHON_ENABLE_INIT_INDEXING):
        try:
            # Todo: refactor this function
            self.load_function_metadata(
                function_app_directory,
                caller_info="functions_metadata_request")
        except Exception as ex:
            # Todo: save the exception
            self._function_metadata_exception = ex


async def function_load_request(self, request):
    # no op because indexing in init / env reload


async def invocation_request(self, request):
    invocation_time = datetime.now()
    invoc_request = request.invocation_request
    invocation_id = invoc_request.invocation_id
    function_id = invoc_request.function_id
    http_v2_enabled = False

    # Removed loop setting info

    try:
        # Todo: refactor functions.py
        fi: functions.FunctionInfo = self._functions.get_function(
            function_id)
        assert fi is not None

        function_invocation_logs: List[str] = [
            'Received FunctionInvocationRequest',
            f'request ID: {self.request_id}',
            f'function ID: {function_id}',
            f'function name: {fi.name}',
            f'invocation ID: {invocation_id}',
            f'function type: {"async" if fi.is_async else "sync"}',
            f'timestamp (UTC): {invocation_time}'
        ]
        if not fi.is_async:
            function_invocation_logs.append(
                f'sync threadpool max workers: '
                f'{self.get_sync_tp_workers_set()}'
            )
        logger.info(', '.join(function_invocation_logs))

        args = {}

        http_v2_enabled = self._functions.get_function(function_id) \
                              .is_http_func and \
            HttpV2Registry.http_v2_enabled()

        for pb in invoc_request.input_data:
            pb_type_info = fi.input_types[pb.name]
            if bindings.is_trigger_binding(pb_type_info.binding_name):
                trigger_metadata = invoc_request.trigger_metadata
            else:
                trigger_metadata = None

            args[pb.name] = bindings.from_incoming_proto(
                pb_type_info.binding_name,
                pb,
                trigger_metadata=trigger_metadata,
                pytype=pb_type_info.pytype,
                shmem_mgr=self._shmem_mgr,
                function_name=self._functions.get_function(
                    function_id).name,
                is_deferred_binding=pb_type_info.deferred_bindings_enabled)

        if http_v2_enabled:
            http_request = await http_coordinator.get_http_request_async(
                invocation_id)

            trigger_arg_name = fi.trigger_metadata.get('param_name')
            func_http_request = args[trigger_arg_name]
            await sync_http_request(http_request, func_http_request)
            args[trigger_arg_name] = http_request

        fi_context = self._get_context(invoc_request, fi.name,
                                       fi.directory)

        # Use local thread storage to store the invocation ID
        # for a customer's threads
        fi_context.thread_local_storage.invocation_id = invocation_id
        if fi.requires_context:
            args['context'] = fi_context

        if fi.output_types:
            for name in fi.output_types:
                args[name] = bindings.Out()

        if fi.is_async:
            if self._azure_monitor_available:
                self.configure_opentelemetry(fi_context)

            call_result = \
                await self._run_async_func(fi_context, fi.func, args)
        else:
            call_result = await self._loop.run_in_executor(
                self._sync_call_tp,
                self._run_sync_func,
                invocation_id, fi_context, fi.func, args)

        if call_result is not None and not fi.has_return:
            raise RuntimeError(
                f'function {fi.name!r} without a $return binding'
                'returned a non-None value')

        if http_v2_enabled:
            http_coordinator.set_http_response(invocation_id, call_result)

        output_data = []
        cache_enabled = self._function_data_cache_enabled
        if fi.output_types:
            for out_name, out_type_info in fi.output_types.items():
                val = args[out_name].get()
                if val is None:
                    # TODO: is the "Out" parameter optional?
                    # Can "None" be marshaled into protos.TypedData?
                    continue

                param_binding = bindings.to_outgoing_param_binding(
                    out_type_info.binding_name, val,
                    pytype=out_type_info.pytype,
                    out_name=out_name, shmem_mgr=self._shmem_mgr,
                    is_function_data_cache_enabled=cache_enabled)
                output_data.append(param_binding)

        return_value = None
        if fi.return_type is not None and not http_v2_enabled:
            return_value = bindings.to_outgoing_proto(
                fi.return_type.binding_name,
                call_result,
                pytype=fi.return_type.pytype,
            )

        # Actively flush customer print() function to console
        sys.stdout.flush()

        # Todo: return appropriate dict
        return {}

    except Exception as ex:
        if http_v2_enabled:
            http_coordinator.set_http_response(invocation_id, ex)

        # Todo: return appropriate dict
        return {}


async def function_environment_reload_request(self, request):
    """Only runs on Linux Consumption placeholder specialization.
    This is called only when placeholder mode is true. On worker restarts
    worker init request will be called directly.
    """
    try:

        func_env_reload_request = \
            request.function_environment_reload_request
        directory = func_env_reload_request.function_app_directory

        if is_envvar_true(PYTHON_ENABLE_DEBUG_LOGGING):
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.DEBUG)

        # calling load_binding_registry again since the
        # reload_customer_libraries call clears the registry
        bindings.load_binding_registry()

        capabilities = {}
        if get_app_setting(
                setting=PYTHON_ENABLE_OPENTELEMETRY,
                default_value=PYTHON_ENABLE_OPENTELEMETRY_DEFAULT):
            self.initialize_azure_monitor()

            if self._azure_monitor_available:
                capabilities[WORKER_OPEN_TELEMETRY_ENABLED] = (
                    TRUE)

        if is_envvar_true(PYTHON_ENABLE_INIT_INDEXING):
            try:
                # Todo: save and handle all this data appropriately
                self.load_function_metadata(
                    directory,
                    caller_info="environment_reload_request")

                if HttpV2Registry.http_v2_enabled():
                    capabilities[HTTP_URI] = \
                        initialize_http_server(self._host)
                    capabilities[REQUIRES_ROUTE_PARAMETERS] = TRUE
            except HttpServerInitError:
                raise
            except Exception as ex:
                self._function_metadata_exception = ex

        # Change function app directory
        if getattr(func_env_reload_request,
                   'function_app_directory', None):
            self._change_cwd(
                func_env_reload_request.function_app_directory)

        # Todo: return appropriate dict
        return {}

    except Exception as ex:
        # Todo: save and surface exception
        return {}
