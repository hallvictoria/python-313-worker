# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import asyncio
import concurrent
import functools

from typing import Any, Optional

from .constants import PYTHON_THREADPOOL_THREAD_COUNT
from .env_state import get_app_setting
from .validators import tp_max_workers_validator

from ..otel import OTelManager, configure_opentelemetry


def get_current_loop():
    return asyncio.events.get_event_loop()


def execute(function, args) -> Any:
    return function(**args)


def run_sync_func(invocation_id, context, func, params):
    # This helper exists because we need to access the current
    # invocation_id from ThreadPoolExecutor's threads.
    context.thread_local_storage.invocation_id = invocation_id
    try:
        if OTelManager.get_azure_monitor_available():
            configure_opentelemetry(context)
        return functools.partial(execute, context, func)(params)
    finally:
        context.thread_local_storage.invocation_id = None

