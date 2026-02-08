import os
import sys

import envcipher


envcipher.load()

from config import setup_logging
from loguru import logger
from tasks import error_prone_task, redrive_from_dlq, user_task


setup_logging(log_level=os.getenv("LOGGING_LEVEL", "INFO"))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "redrive":
            redrive_from_dlq.delay()
            logger.info("Redrive from DLQ started")
        elif sys.argv[1] == "user":
            user_task.delay()
            logger.info("User task started")
        elif sys.argv[1] == "error":
            error_prone_task.delay()
            logger.info("Error prone task started")
        else:
            logger.error("Invalid argument")
    else:
        logger.error(
            "Missing argument. Please provide one of the following: redrive, user, error"
        )
