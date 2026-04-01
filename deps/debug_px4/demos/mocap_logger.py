import argparse
import struct
import time

import zenoh

MAGIC = b"MCP1"
HEADER_STRUCT = struct.Struct("<4sI")
TOPIC_HDR_STRUCT = struct.Struct("<HH")
FIELD_HDR_STRUCT = struct.Struct("<H")
FRAME_HDR_STRUCT = struct.Struct("<QHI")


def write_header(f, topics: dict[str, dict]) -> None:
    f.write(HEADER_STRUCT.pack(MAGIC, len(topics)))
    for keyexpr, info in topics.items():
        key_bytes = keyexpr.encode("utf-8")
        fmt_bytes = info["format"].encode("utf-8")
        fields = info["fields"]
        f.write(TOPIC_HDR_STRUCT.pack(len(key_bytes), len(fields)))
        f.write(FIELD_HDR_STRUCT.pack(len(fmt_bytes)))
        f.write(key_bytes)
        f.write(fmt_bytes)
        for field in fields:
            field_bytes = field.encode("utf-8")
            f.write(FIELD_HDR_STRUCT.pack(len(field_bytes)))
            f.write(field_bytes)
    f.flush()


def main():
    parser = argparse.ArgumentParser(description="Zenoh subscriber -> .mocap file logger")
    parser.add_argument("--output", "-o", default="log.mocap", help="Output .mocap file path")
    parser.add_argument(
        "--keyexpr",
        "-k",
        default="neupilot/debug/**",
        help="Zenoh keyexpr to subscribe (supports wildcards)",
    )
    parser.add_argument("--mode", "-m", default="peer", choices=["peer", "client"])
    parser.add_argument("--locator", "-l", default="")
    args = parser.parse_args()

    from demos.fake_publisher import TOPICS

    frame_count = 0
    topic_index: dict[str, int] = {k: i for i, k in enumerate(TOPICS)}

    with open(args.output, "wb") as f:
        write_header(f, TOPICS)
        print(f"[mocap_logger] header written -> {args.output}")
        print(f"[mocap_logger] subscribing to: {args.keyexpr}")

        conf = zenoh.Config()
        conf.insert_json5("mode", f'"{args.mode}"')
        if args.locator:
            conf.insert_json5("connect/endpoints", f'["{args.locator}"]')
        session = zenoh.open(conf)

        def _on_sample(sample: zenoh.Sample):
            nonlocal frame_count
            recv_t = int(time.time() * 1e6)
            key = str(sample.key_expr)
            idx = topic_index.get(key)
            if idx is None:
                return
            payload = bytes(sample.payload)
            f.write(FRAME_HDR_STRUCT.pack(recv_t, idx, len(payload)))
            f.write(payload)
            f.flush()
            frame_count += 1
            if frame_count % 50 == 0:
                print(f"[mocap_logger] {frame_count} frames, last: {key} ({len(payload)} B)")

        sub = session.declare_subscriber(args.keyexpr, _on_sample)

        try:
            print("[mocap_logger] logging... Ctrl+C to stop")
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print(f"\n[mocap_logger] stopped, {frame_count} frames written to {args.output}")
        finally:
            sub.undeclare()
            session.close()


if __name__ == "__main__":
    main()
