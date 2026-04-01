import argparse
import struct
import time

MAGIC = b"MCP1"
HEADER_STRUCT = struct.Struct("<4sI")
TOPIC_HDR_STRUCT = struct.Struct("<HH")
FIELD_HDR_STRUCT = struct.Struct("<H")
FRAME_HDR_STRUCT = struct.Struct("<QHI")


def read_header(f) -> tuple[dict[int, dict], int]:
    raw = f.read(HEADER_STRUCT.size)
    magic, n_topics = HEADER_STRUCT.unpack(raw)
    if magic != MAGIC:
        raise ValueError(f"invalid magic: {magic!r}, expected {MAGIC!r}")

    topics: dict[int, dict] = {}
    for idx in range(n_topics):
        raw = f.read(TOPIC_HDR_STRUCT.size)
        key_len, n_fields = TOPIC_HDR_STRUCT.unpack(raw)
        fmt_len_raw = f.read(FIELD_HDR_STRUCT.size)
        fmt_len = FIELD_HDR_STRUCT.unpack(fmt_len_raw)[0]
        keyexpr = f.read(key_len).decode("utf-8")
        fmt_str = f.read(fmt_len).decode("utf-8")
        fields = []
        for _ in range(n_fields):
            fl_raw = f.read(FIELD_HDR_STRUCT.size)
            fl = FIELD_HDR_STRUCT.unpack(fl_raw)[0]
            fields.append(f.read(fl).decode("utf-8"))
        topics[idx] = {
            "keyexpr": keyexpr,
            "format": fmt_str,
            "fields": fields,
        }

    return topics, f.tell()


def read_frames(f, topics: dict[int, dict], max_frames: int = 0) -> list[dict]:
    frames = []
    while True:
        raw = f.read(FRAME_HDR_STRUCT.size)
        if not raw or len(raw) < FRAME_HDR_STRUCT.size:
            break
        recv_ts, topic_idx, payload_len = FRAME_HDR_STRUCT.unpack(raw)
        payload = f.read(payload_len)
        if len(payload) < payload_len:
            break

        topic = topics.get(topic_idx)
        if topic is None:
            continue

        values = struct.unpack(topic["format"], payload)
        frame = {
            "recv_timestamp_us": recv_ts,
            "topic": topic["keyexpr"],
        }
        for i, field in enumerate(topic["fields"]):
            frame[field] = values[i] if i < len(values) else None
        frames.append(frame)

        if max_frames > 0 and len(frames) >= max_frames:
            break

    return frames


def main():
    parser = argparse.ArgumentParser(description="Read and display .mocap log files")
    parser.add_argument("file", help="Path to .mocap file")
    parser.add_argument("--limit", "-n", type=int, default=10, help="Number of frames to display")
    parser.add_argument("--topics", action="store_true", help="Show topic info only")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    args = parser.parse_args()

    with open(args.file, "rb") as f:
        topics, header_end = read_header(f)

        print(f"=== .mocap file: {args.file} ===")
        print(f"  header size: {header_end} bytes")
        print(f"  topics: {len(topics)}")
        for idx, t in topics.items():
            print(f"    [{idx}] {t['keyexpr']}")
            print(f"        format: {t['format']}")
            print(f"        fields: {', '.join(t['fields'])}")

        if args.topics:
            return

        if args.stats:
            f.seek(header_end)
            all_frames = read_frames(f, topics, max_frames=0)
            print("\n=== Statistics ===")
            print(f"  total frames: {len(all_frames)}")
            by_topic: dict[str, list] = {}
            for fr in all_frames:
                by_topic.setdefault(fr["topic"], []).append(fr)
            for key, frames in by_topic.items():
                ts_list = [fr["recv_timestamp_us"] for fr in frames]
                dur = (ts_list[-1] - ts_list[0]) / 1e6
                avg_hz = len(frames) / dur if dur > 0 else 0
                print(f"  {key}: {len(frames)} frames, avg {avg_hz:.1f} Hz, {dur:.2f}s")
            return

        f.seek(header_end)
        frames = read_frames(f, topics, max_frames=args.limit)

        print(f"\n=== First {len(frames)} frames ===")
        for i, fr in enumerate(frames):
            ts_s = fr.pop("recv_timestamp_us") / 1e6
            topic = fr.pop("topic")
            time_str = time.strftime("%H:%M:%S", time.localtime(ts_s)) + f".{int(ts_s % 1 * 1000):03d}"
            print(f"  [{i:4d}] {time_str} | {topic}")
            for k, v in fr.items():
                if isinstance(v, float):
                    print(f"         {k}: {v:+.6f}")
                else:
                    print(f"         {k}: {v}")


if __name__ == "__main__":
    main()
