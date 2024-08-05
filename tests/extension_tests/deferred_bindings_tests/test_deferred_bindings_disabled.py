# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import sys
import unittest

import azure.functions as func
from tests.utils import testutils

from azure_functions_worker import protos
from azure_functions_worker.bindings import meta


DEFERRED_BINDINGS_DISABLED_DIR = testutils.EXTENSION_TESTS_FOLDER / \
    'deferred_bindings_tests' / \
    'deferred_bindings_functions' / \
    'deferred_bindings_disabled'


@unittest.skipIf(sys.version_info.minor <= 8, "The base extension"
                                              "is only supported for 3.9+.")
class TestDeferredBindingsDisabled(testutils.AsyncTestCase):

    async def test_deferred_bindings_disabled_metadata(self):
        async with testutils.start_mockhost(
                script_root=DEFERRED_BINDINGS_DISABLED_DIR) as host:
            await host.init_worker()
            r = await host.get_functions_metadata()
            self.assertIsInstance(r.response, protos.FunctionMetadataResponse)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

    @testutils.retryable_test(3, 5)
    async def test_deferred_bindings_disabled_log(self):
        async with testutils.start_mockhost(
                script_root=DEFERRED_BINDINGS_DISABLED_DIR) as host:
            await host.init_worker()
            r = await host.get_functions_metadata()
            disabled_log_present = False
            for log in r.logs:
                message = log.message
                if "Deferred bindings enabled: False" in message:
                    disabled_log_present = True
                    break
            self.assertTrue(disabled_log_present)


@unittest.skipIf(sys.version_info.minor <= 8, "The base extension"
                                              "is only supported for 3.9+.")
class TestDeferredBindingsDisabledHelpers(testutils.AsyncTestCase):

    async def test_check_deferred_bindings_disabled(self):
        """
        check_deferred_bindings_enabled checks if deferred bindings is enabled at fx
        and single binding level.

        The first bool represents if deferred bindings is enabled at a fx level. This
        means that at least one binding in the function is a deferred binding type.

        The second represents if the current binding is deferred binding. If this is
        True, then deferred bindings must also be enabled at the function level.

        Test: type is not supported, deferred_bindings_enabled is not yet set
        """
        async with testutils.start_mockhost(
                script_root=DEFERRED_BINDINGS_DISABLED_DIR) as host:
            await host.init_worker()
            self.assertEqual(meta.check_deferred_bindings_enabled(
                func.InputStream, False), (False, False))