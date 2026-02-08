# Sample Celery DLQ

[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A reference implementation of the dead letter queue pattern for Celery, featuring automatic retries with exponential backoff and manual task redrive capabilities.

---

## Installation

<details open>
<summary><strong>Using uv</strong></summary>

```bash
git clone https://github.com/iamprecieee/sample-celery-dlq
cd sample-celery-dlq
uv sync
```

</details>

<details>
<summary><strong>Using pip</strong></summary>

```bash
git clone https://github.com/iamprecieee/sample-celery-dlq
cd sample-celery-dlq
pip install -r requirements.txt
```

</details>

---

## Prerequisites

- Python 3.13+
- Redis server running
- [envcipher](https://github.com/iamprecieee/envcipher) for encrypted environment variables

---

## Configuration

Create a `.env` file with:

```bash
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TASK_MAX_RETRIES=5
CELERY_TASK_RETRY_BACKOFF_MAX=10
LOGGING_LEVEL=DEBUG
```

Encrypt with envcipher:

```bash
envcipher init
envcipher lock
```

---

## Usage

### Start Worker

```bash
uv run celery -A tasks worker -l info -Q default,user,monitoring --pool=solo
```

### Dispatch Tasks

```bash
uv run main.py error    # Trigger error-prone task (will fail and go to DLQ)
uv run main.py user     # Trigger user task (succeeds)
uv run main.py redrive  # Redrive tasks from DLQ back to original queues
```

<details>
<summary><strong>Inspect DLQ</strong></summary>

```bash
# View all failed tasks (replace <redis-host> with your Redis host)
redis-cli -h <redis-host> LRANGE dlq_storage 0 -1

# Clear DLQ
redis-cli -h <redis-host> DEL dlq_storage
```

</details>

---

## How It Works

| Component | Description |
|-----------|-------------|
| `BaseTask` | Custom task class with auto-retry, exponential backoff, and DLQ handling |
| `dlq_storage` | Redis list storing failed task metadata (separate from Celery queues) |
| `redrive_from_dlq` | Task that reads from DLQ and re-queues tasks to their original queues |

### Flow

1. Task fails after max retries
2. `on_failure` stores task metadata in `dlq_storage` Redis list
3. Call `redrive_from_dlq` to re-queue failed tasks when ready
4. Tasks sent back to original queue via `app.send_task()`

---

## Configuration Options

| Setting | Purpose |
|---------|---------|
| `task_acks_late=True` | Acknowledge task only after completion |
| `task_reject_on_worker_lost=True` | Requeue task if worker crashes |
| `autoretry_for` | Exception types to auto-retry |
| `max_retries` | Maximum retry attempts before DLQ |
| `retry_backoff` | Enable exponential backoff |
| `retry_jitter` | Add randomness to retry delays |

---

## FAQ

<details>
<summary>Why use a Redis list instead of a Celery queue for DLQ?</summary>

Using a Celery queue causes the worker to immediately consume and re-execute failed tasks, creating an infinite loop. A Redis list stores tasks passively until you explicitly redrive them.

</details>

<details>
<summary>How do I add more queues?</summary>

Add queues to the worker command and use `queue="queue_name"` in your task decorators:

```bash
uv run celery -A tasks worker -Q default,user,monitoring,emails --pool=solo
```

```python
@shared_task(base=BaseTask, queue="emails")
def send_email():
    pass
```

</details>

---

## License

[MIT](LICENSE)
