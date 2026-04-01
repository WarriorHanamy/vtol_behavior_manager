import struct
import time

import numpy as np
import zenoh

NOISE_STD = 0.01


def _n(v: float) -> float:
    return v + np.random.normal(0.0, NOISE_STD)


TOPICS = {
    "neupilot/debug/acc_rates_control": {
        "format": "<Qffff3fffffBBB",
        "fields": [
            "timestamp",
            "thrust_axis_specific_force_sp",
            "thrust_axis_specific_force",
            "hover_thrust_estimate",
            "rates_sp_roll",
            "rates_sp_pitch",
            "rates_sp_yaw",
            "thrust_body_z_ff",
            "thrust_body_z_feedback",
            "thrust_body_z_sp",
            "thrust_bias",
            "hte_valid",
            "hte_active",
        ],
    },
    "neupilot/debug/vehicle_local_position": {
        "format": "<Q3f3f3f4f",
        "fields": [
            "timestamp",
            "ned_pos_x",
            "ned_pos_y",
            "ned_pos_z",
            "ned_vel_x",
            "ned_vel_y",
            "ned_vel_z",
            "ned_acc_x",
            "ned_acc_y",
            "ned_acc_z",
            "ned_quat_frd_w",
            "ned_quat_frd_x",
            "ned_quat_frd_y",
            "ned_quat_frd_z",
        ],
    },
}


def _make_acc_rates_control(t_us: int, t_s: float) -> bytes:
    return struct.pack(
        "<Qffff3fffffBBB",
        t_us,
        _n(-9.81 + 0.5 * np.sin(2.0 * np.pi * 0.5 * t_s)),
        _n(-9.81 + 0.3 * np.sin(2.0 * np.pi * 0.5 * t_s + 0.2)),
        _n(0.55 + 0.05 * np.sin(2.0 * np.pi * 0.1 * t_s)),
        _n(0.1 * np.sin(2.0 * np.pi * 0.3 * t_s)),
        _n(-0.05 * np.cos(2.0 * np.pi * 0.3 * t_s)),
        _n(0.02 * np.sin(2.0 * np.pi * 0.2 * t_s)),
        _n(0.4 + 0.1 * np.sin(2.0 * np.pi * 0.5 * t_s)),
        _n(-0.2 + 0.05 * np.cos(2.0 * np.pi * 0.5 * t_s)),
        _n(0.3),
        _n(0.01 * np.sin(2.0 * np.pi * 0.2 * t_s)),
        0.0,
        1,
        1,
        0,
    )


def _make_vehicle_local_position(t_us: int, t_s: float) -> bytes:
    ned_pos_x = _n(10.0 * np.sin(2.0 * np.pi * 0.05 * t_s))
    ned_pos_y = _n(5.0 * np.cos(2.0 * np.pi * 0.05 * t_s))
    ned_pos_z = _n(-3.0 + 0.5 * np.sin(2.0 * np.pi * 0.02 * t_s))
    ned_vel_x = _n(10.0 * 2.0 * np.pi * 0.05 * np.cos(2.0 * np.pi * 0.05 * t_s))
    ned_vel_y = _n(-5.0 * 2.0 * np.pi * 0.05 * np.sin(2.0 * np.pi * 0.05 * t_s))
    ned_vel_z = _n(0.5 * 2.0 * np.pi * 0.02 * np.cos(2.0 * np.pi * 0.02 * t_s))
    yaw = 0.3 * np.sin(2.0 * np.pi * 0.1 * t_s)
    q_w = np.cos(yaw / 2.0)
    q_x = 0.0
    q_y = 0.0
    q_z = np.sin(yaw / 2.0)
    if q_w < 0:
        q_w, q_x, q_y, q_z = -q_w, -q_x, -q_y, -q_z
    return struct.pack(
        "<Q3f3f3f4f",
        t_us,
        ned_pos_x,
        ned_pos_y,
        ned_pos_z,
        ned_vel_x,
        ned_vel_y,
        ned_vel_z,
        0.0,
        0.0,
        0.0,
        _n(q_w),
        _n(q_x),
        _n(q_y),
        _n(q_z),
    )


GENERATORS = {
    "neupilot/debug/acc_rates_control": _make_acc_rates_control,
    "neupilot/debug/vehicle_local_position": _make_vehicle_local_position,
}


def main():
    conf = zenoh.Config()
    conf.insert_json5("mode", '"peer"')
    session = zenoh.open(conf)

    publishers = {}
    for keyexpr in TOPICS:
        publishers[keyexpr] = session.declare_publisher(keyexpr)
        print(f"[publisher] declared: {keyexpr}")

    rate_hz = 50.0
    dt = 1.0 / rate_hz
    print(f"[publisher] publishing at {rate_hz} Hz, Ctrl+C to stop")

    try:
        t0 = time.monotonic()
        while True:
            t_us = int(time.time() * 1e6)
            t_s = time.monotonic() - t0
            row = []
            for keyexpr, gen in GENERATORS.items():
                payload = gen(t_us, t_s)
                publishers[keyexpr].put(payload)
                fields = TOPICS[keyexpr]["fields"]
                values = struct.unpack(TOPICS[keyexpr]["format"], payload)
                pairs = [f"{f}={v:.4f}" if isinstance(v, float) else f"{f}={v}" for f, v in zip(fields, values)]
                row.append(f"{keyexpr}: {{{', '.join(pairs)}}}")
            print(f"[t={t_s:.2f}s] " + " | ".join(row))
            time.sleep(dt)
    except KeyboardInterrupt:
        print("\n[publisher] stopped")
    finally:
        for pub in publishers.values():
            pub.undeclare()
        session.close()


if __name__ == "__main__":
    main()
