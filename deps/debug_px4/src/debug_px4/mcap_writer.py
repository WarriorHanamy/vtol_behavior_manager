import time
from typing import BinaryIO

from mcap.writer import Writer

from debug_px4.topics import TopicHandler


class McapRecorder:
    def __init__(self, stream: BinaryIO, topic: str, handler: TopicHandler):
        self._writer = Writer(stream)
        self._writer.start(library="debug-px4")
        schema_id = self._writer.register_schema(
            name=topic,
            encoding="jsonschema",
            data=handler.get_json_schema(),
        )
        self._channel_id = self._writer.register_channel(
            topic=topic,
            message_encoding="json",
            schema_id=schema_id,
            metadata={"source": "zenoh"},
        )
        self._handler = handler
        self._sequence = 0

    def write(self, data: bytes) -> None:
        now = time.time_ns()
        self._writer.add_message(
            channel_id=self._channel_id,
            log_time=now,
            publish_time=now,
            sequence=self._sequence,
            data=self._handler.encode_json(data),
        )
        self._sequence += 1

    def finish(self) -> None:
        self._writer.finish()
