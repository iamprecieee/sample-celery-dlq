import json
import os
import secrets
import time

import envcipher
import redis
from celery import Celery, shared_task, signals, Task
from config import setup_logging
from loguru import logger


envcipher.load()

app = Celery(
    "sample-celery-dlq",
    broker=os.getenv("CELERY_BROKER_URL"),
    backend=os.getenv("CELERY_RESULT_BACKEND"),
)

app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


@signals.setup_logging.connect
def config_loggers(*args, **kwargs):
    setup_logging(log_level=os.getenv("LOGGING_LEVEL", "INFO"))


class BaseTask(Task):
    autoretry_for = (Exception,)
    max_retries = int(os.getenv("CELERY_TASK_MAX_RETRIES"))
    retry_backoff = True
    retry_backoff_max = int(os.getenv("CELERY_TASK_RETRY_BACKOFF_MAX"))
    retry_jitter = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task {task_id} failed: {exc}")

        original_queue = (
            self.request.delivery_info.get("routing_key")
            if self.request.delivery_info
            else "default"
        )

        try:
            client = redis.from_url(os.getenv("CELERY_BROKER_URL"))
            dlq_entry = json.dumps(
                {
                    "task_id": task_id,
                    "task_name": self.name,
                    "args": args,
                    "kwargs": kwargs,
                    "original_queue": original_queue,
                    "error": str(exc),
                }
            )
            client.rpush("dlq_storage", dlq_entry)
            logger.debug(f"Task {task_id} moved to redis DLQ")
        except Exception as e:
            logger.error(f"Failed to move task {task_id} to redis DLQ: {e}")

        super().on_failure(exc, task_id, args, kwargs, einfo)


@shared_task(base=BaseTask, queue="monitoring")
def redrive_from_dlq():
    client = redis.from_url(os.getenv("CELERY_BROKER_URL"))
    count = 0

    while True:
        message = client.lpop("dlq_storage")
        if not message:
            break

        try:
            task_data = json.loads(message)
            task_id = task_data.get("task_id")
            target_queue = task_data.get("original_queue", "default")

            logger.debug(f"Task data: {task_data}")
            app.send_task(
                task_data.get("task_name"),
                args=task_data.get("args", []),
                kwargs=task_data.get("kwargs", {}),
                queue=target_queue,
            )

            logger.debug(f"Redrove task {task_id} from DLQ to {target_queue}")
            count += 1
        except Exception as e:
            logger.error(f"Failed to redrive message: {e}")
            client.rpush("dlq_storage", message)
            break

    logger.info(f"Redrove {count} tasks from DLQ")
    return count


@shared_task(base=BaseTask, queue="default")
def error_prone_task():
    raise Exception("Something went wrong")


@shared_task(base=BaseTask, queue="user")
def user_task():
    user_id = secrets.token_hex(16)

    logger.info(f"Processing user {user_id}")
    time.sleep(5)
    logger.info(f"User {user_id} processed")
    return user_id
