# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import asyncio
import unittest

from typing import Any

from tests.utils import testutils
import tests.protos as protos

from azure_functions_worker.handle_event import (Status,
                                                 worker_init_request,
                                                 functions_metadata_request,
                                                 function_environment_reload_request)


class WorkerRequest:
    def __init__(self, name: str, request: Any, properties: dict):
        self.name = name
        self.request = request
        self.properties = properties


class InnerRequest:
    def __init__(self, name: Any):
        self.worker_init_request = name
        self.function_environment_reload_request = name


class InnerInnerRequest:
    def __init__(self, name: Any):
        self.capabilities = name
        self.function_app_directory = "C:\\Users\\victoriahall\\Documents\\repos\\azure-functions-python-worker-313\\tests\\unit_tests"


class TestObjects(unittest.TestCase):
    def test_stringify_enum(self):
        pass

    def test_status(self):
        pass

    def test_worker_response(self):
        pass


class TestHandleEvent(testutils.AsyncTestCase):
    async def test_worker_init_request(self):
        worker_request = WorkerRequest(name='worker_init_request',
                                       request=InnerRequest(InnerInnerRequest('hello')),
                                       properties={'host': '123',
                                                   'protos': protos})
        result = await worker_init_request(worker_request)
        self.assertEqual(result._name, "worker_init_request")
        self.assertEqual(result._status, Status.SUCCESS)
        self.assertEqual(result._result.get('capabilities'), {'RawHttpBodyBytes': 'true', 'RpcHttpBodyOnly': 'true', 'RpcHttpTriggerMetadataRemoved': 'true', 'SharedMemoryDataTransfer': 'true', 'TypedDataCollection': 'true', 'WorkerStatus': 'true'})
        self.assertEqual(result._exception, {'message': None, 'status_code': 200, 'type': None})

    def test_worker_init_request_with_streaming(self):
        pass

    def test_worker_init_request_with_exception(self):
        pass

    async def test_functions_metadata_request(self):
        result = asyncio.run(self.run_init_then_meta())
        self.assertEqual(result._name, "functions_metadata_request")
        self.assertEqual(result._status, Status.SUCCESS)
        self.assertIsNotNone(result._result.get('function_metadata'))  # checked locally, needs more in-depth test perchance
        self.assertEqual(result._exception, {'message': None, 'status_code': 200, 'type': None})

    async def run_init_then_meta(self):
        worker_request = WorkerRequest(name='worker_init_request',
                                       request=InnerRequest(InnerInnerRequest('hello')),
                                       properties={'host': '123',
                                                   'protos': protos})
        _ = await worker_init_request(worker_request)
        result = await functions_metadata_request("")
        return result

    def test_functions_metadata_request_with_exception(self):
        pass

    def test_invocation_request_sync(self):
        pass

    def test_invocation_request_async(self):
        pass

    def test_invocation_request_with_exception(self):
        pass

    async def test_function_environment_reload_request(self):
        worker_request = WorkerRequest(name='function_environment_reload_request',
                                       request=InnerRequest(InnerInnerRequest('hello')),
                                       properties={'host': '123',
                                                   'protos': protos})
        result = await function_environment_reload_request(worker_request)
        self.assertEqual(result._name, "function_environment_reload_request")
        self.assertEqual(result._status, Status.SUCCESS)
        self.assertEqual(result._result.get('capabilities'), {})
        self.assertEqual(result._exception, {'message': None, 'status_code': 200, 'type': None})

    def test_function_environment_reload_request_with_streaming(self):
        pass

    def test_function_environment_reload_request_with_exception(self):
        pass

    def test_load_function_metadata(self):
        pass

    def test_index_functions(self):
        pass
