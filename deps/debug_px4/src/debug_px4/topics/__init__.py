from typing import Any, Protocol

from debug_px4.topics.acc_rates_control import AccRatesControlHandler


class TopicHandler(Protocol):
    def decode(self, data: bytes) -> Any: ...

    def get_plot_fields(self) -> list[str]: ...

    def get_json_schema(self) -> bytes: ...

    def encode_json(self, data: bytes) -> bytes: ...


_topic_handlers: dict[str, Any] = {
    "neupilot/debug/acc_rates_control": AccRatesControlHandler(),
}


def get_topic_handler(keyexpr: str) -> TopicHandler | None:
    return _topic_handlers.get(keyexpr)
