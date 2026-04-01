import argparse
from pathlib import Path

from debug_px4.mcap_writer import McapRecorder
from debug_px4.subscriber import ZenohSubscriber
from debug_px4.topics import get_topic_handler
from debug_px4.viz.plot import RealTimePlot


def main():
    parser = argparse.ArgumentParser(description="PX4 Zenoh debug subscriber")
    parser.add_argument("--topic", "-t", default="neupilot/debug/acc_rates_control", help="Zenoh keyexpr")
    parser.add_argument("--mode", "-m", default="peer", choices=["peer", "client"], help="Zenoh mode")
    parser.add_argument("--locator", "-l", default="", help="Zenoh locator (e.g., tcp/127.0.0.1:7447)")
    parser.add_argument("--plot", "-p", action="store_true", help="Enable matplotlib visualization")
    parser.add_argument("--mcap-output", help="Write standard MCAP output to this file")
    args = parser.parse_args()

    handler = get_topic_handler(args.topic)
    if handler is None:
        print(f"Unknown topic: {args.topic}")
        return 1

    if args.plot:
        plot = RealTimePlot(handler)
        with ZenohSubscriber() as sub:
            sub.connect(mode=args.mode, locator=args.locator)
            sub.subscribe(args.topic, plot.on_data)
            plot.show()
    elif args.mcap_output:
        output_path = Path(args.mcap_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as stream:
            recorder = McapRecorder(stream=stream, topic=args.topic, handler=handler)
            with ZenohSubscriber() as sub:
                sub.connect(mode=args.mode, locator=args.locator)
                sub.subscribe(args.topic, recorder.write)
                try:
                    input(f"Recording MCAP to {output_path}. Press Enter to exit...")
                finally:
                    recorder.finish()
    else:

        def _print(data: bytes):
            msg = handler.decode(data)
            print(msg)

        with ZenohSubscriber() as sub:
            sub.connect(mode=args.mode, locator=args.locator)
            sub.subscribe(args.topic, _print)
            input("Press Enter to exit...")

    return 0


if __name__ == "__main__":
    exit(main())
