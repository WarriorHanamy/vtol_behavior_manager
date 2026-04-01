from __future__ import annotations

from pathlib import Path
from typing import Any

from debug_px4.mcap_writer import McapRecorder
from debug_px4.subscriber import ZenohSubscriber
from debug_px4.topics import get_topic_handler
from debug_px4.viz.plot import RealTimePlot


class Entrypoint:
    def __init__(self, topic: str, *, mode: str = "peer", locator: str = ""):
        self._topic = topic
        self._mode = mode
        self._locator = locator
        self._handler = get_topic_handler(topic)
        if self._handler is None:
            raise ValueError(f"Unknown topic: {topic}")
        self._sub = ZenohSubscriber()

    def __enter__(self) -> Entrypoint:
        self._sub.connect(self._mode, self._locator)
        return self

    def __exit__(self, *args: Any) -> None:
        self._sub.close()

    def print(self) -> None:
        handler = self._handler

        def _cb(data: bytes) -> None:
            msg = handler.decode(data)
            print(msg)

        self._sub.subscribe(self._topic, _cb)
        try:
            input("Press Enter to exit...")
        except KeyboardInterrupt:
            pass

    def plot(self) -> None:
        viz = RealTimePlot(self._handler)
        self._sub.subscribe(self._topic, viz.on_data)
        viz.show()

    def record(self, output: str | Path) -> None:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as stream:
            recorder = McapRecorder(stream=stream, topic=self._topic, handler=self._handler)
            self._sub.subscribe(self._topic, recorder.write)
            try:
                input(f"Recording MCAP to {output_path}. Press Enter to exit...")
            except KeyboardInterrupt:
                pass
            finally:
                recorder.finish()


def subscribe(topic: str, **kwargs: Any) -> None:
    with Entrypoint(topic, **kwargs) as ep:
        ep.print()


def plot(topic: str, **kwargs: Any) -> None:
    with Entrypoint(topic, **kwargs) as ep:
        ep.plot()


def record(topic: str, output: str | Path, **kwargs: Any) -> None:
    with Entrypoint(topic, **kwargs) as ep:
        ep.record(output)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="entrypoint",
        description="PX4 Zenoh debug entrypoint",
    )
    parser.add_argument("action", choices=["subscribe", "plot", "record"], help="Action to perform")
    parser.add_argument("--topic", "-t", default="neupilot/debug/acc_rates_control", help="Zenoh keyexpr")
    parser.add_argument("--mode", "-m", default="peer", choices=["peer", "client"], help="Zenoh mode")
    parser.add_argument("--locator", "-l", default="", help="Zenoh locator")
    parser.add_argument("--output", "-o", help="MCAP output file (for record)")
    args = parser.parse_args()

    kwargs: dict[str, Any] = {"mode": args.mode, "locator": args.locator}

    if args.action == "subscribe":
        subscribe(args.topic, **kwargs)
    elif args.action == "plot":
        plot(args.topic, **kwargs)
    elif args.action == "record":
        if not args.output:
            parser.error("--output is required for record action")
        record(args.topic, args.output, **kwargs)

    return 0


if __name__ == "__main__":
    exit(main())
