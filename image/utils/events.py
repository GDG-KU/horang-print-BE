import json
import time
from typing import Generator, Optional

from django.conf import settings
import redis


def _get_redis_client() -> redis.Redis:
    """Return a Redis client using REDIS_URL or fall back to CELERY_BROKER_URL."""
    url = getattr(settings, "REDIS_URL", None) or getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/0")
    # decode_responses=True -> pubsub payloads are str instead of bytes
    return redis.Redis.from_url(url, decode_responses=True)


def _session_channel(session_uuid: str) -> str:
    return f"session:{session_uuid}"


def publish_session_event(session_uuid: str, event: str, data: dict) -> None:
    """Publish a JSON payload to the session channel.

    Payload schema: {"event": str, "data": object}
    """
    payload = json.dumps({"event": event, "data": data}, ensure_ascii=False)
    _get_redis_client().publish(_session_channel(session_uuid), payload)


def stream_session_events(session_uuid: str, keepalive_seconds: int = 15) -> Generator[str, None, None]:
    """SSE generator that subscribes to a session channel and yields events.

    Yields Server-Sent Events formatted messages. Sends periodic keepalive comments.
    """
    client = _get_redis_client()
    pubsub = client.pubsub()
    channel = _session_channel(session_uuid)
    pubsub.subscribe(channel)

    last_ping = time.monotonic()
    try:
        # Initial retry hint for proxies
        yield "retry: 3000\n\n"
        while True:
            message: Optional[dict] = pubsub.get_message(timeout=1.0)
            now = time.monotonic()

            if message and message.get("type") == "message":
                try:
                    payload = json.loads(message.get("data") or "{}")
                except json.JSONDecodeError:
                    payload = {"event": "unknown", "data": {"raw": message.get("data")}}

                event_type = payload.get("event") or "message"
                data_obj = payload.get("data") if isinstance(payload.get("data"), (dict, list, str, int, float, bool, type(None))) else {}
                data_str = json.dumps(data_obj, ensure_ascii=False)

                yield f"event: {event_type}\n"
                yield f"data: {data_str}\n\n"
                last_ping = now

            # keepalive
            if now - last_ping >= keepalive_seconds:
                # Comment line to keep the connection alive through proxies
                yield ": ping\n\n"
                last_ping = now
    finally:
        with contextlib.suppress(Exception):
            pubsub.unsubscribe(channel)
            pubsub.close()


