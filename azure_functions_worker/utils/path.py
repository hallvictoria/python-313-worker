# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os


def change_cwd(new_cwd: str):
    if os.path.exists(new_cwd):
        os.chdir(new_cwd)
        logger.info('Changing current working directory to %s', new_cwd)
    else:
        logger.warning('Directory %s is not found when reloading', new_cwd)