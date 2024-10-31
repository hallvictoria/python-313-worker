# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.


from typing import List

# Todo: refactor loader.py
def index_functions(self, function_path: str, function_dir: str):
    indexed_functions = loader.index_function_app(function_path)
    logger.info(
        "Indexed function app and found %s functions",
        len(indexed_functions)
    )

    if indexed_functions:
        fx_metadata_results, fx_bindings_logs = (
            loader.process_indexed_function(
                self._functions,
                indexed_functions,
                function_dir))

        indexed_function_logs: List[str] = []
        indexed_function_bindings_logs = []
        for func in indexed_functions:
            func_binding_logs = fx_bindings_logs.get(func)
            for binding in func.get_bindings():
                deferred_binding_info = func_binding_logs.get(
                    binding.name) \
                    if func_binding_logs.get(binding.name) else ""
                indexed_function_bindings_logs.append((
                    binding.type, binding.name, deferred_binding_info))

            function_log = "Function Name: {}, Function Binding: {}" \
                .format(func.get_function_name(),
                        indexed_function_bindings_logs)
            indexed_function_logs.append(function_log)

        logger.info(
            'Successfully processed FunctionMetadataRequest for '
            'functions: %s. Deferred bindings enabled: %s.', " ".join(
                indexed_function_logs),
            self._functions.deferred_bindings_enabled())

        return fx_metadata_results
