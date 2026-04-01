import json
import struct
from dataclasses import asdict, dataclass
from typing import Self


@dataclass
class AccRatesControlDebug:
    timestamp: int
    thrust_axis_specific_force_sp: float
    thrust_axis_specific_force: float
    hover_thrust_estimate: float
    rates_sp: tuple[float, float, float]
    thrust_body_z_ff: float
    thrust_body_z_feedback: float
    thrust_body_z_sp: float
    thrust_bias: float
    hte_valid: bool
    hte_active: bool

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        unpacked = struct.unpack("<Qffff3fffffBBB", data)
        return cls(
            timestamp=unpacked[0],
            thrust_axis_specific_force_sp=unpacked[1],
            thrust_axis_specific_force=unpacked[2],
            hover_thrust_estimate=unpacked[3],
            rates_sp=(unpacked[4], unpacked[5], unpacked[6]),
            thrust_body_z_ff=unpacked[7],
            thrust_body_z_feedback=unpacked[8],
            thrust_body_z_sp=unpacked[9],
            thrust_bias=unpacked[10],
            hte_valid=bool(unpacked[11]),
            hte_active=bool(unpacked[12]),
        )


class AccRatesControlHandler:
    STRUCT_FORMAT = "<Qffff3fffffBBB"
    FIELD_NAMES = [
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
    ]

    def decode(self, data: bytes) -> AccRatesControlDebug:
        return AccRatesControlDebug.from_bytes(data)

    def get_plot_fields(self) -> list[str]:
        return [
            "thrust_axis_specific_force_sp",
            "thrust_axis_specific_force",
            "hover_thrust_estimate",
            "thrust_body_z_ff",
            "thrust_body_z_feedback",
            "thrust_body_z_sp",
            "thrust_bias",
        ]

    def get_json_schema(self) -> bytes:
        return json.dumps(
            {
                "type": "object",
                "properties": {
                    "timestamp": {"type": "integer"},
                    "thrust_axis_specific_force_sp": {"type": "number"},
                    "thrust_axis_specific_force": {"type": "number"},
                    "hover_thrust_estimate": {"type": "number"},
                    "rates_sp": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 3,
                        "maxItems": 3,
                    },
                    "thrust_body_z_ff": {"type": "number"},
                    "thrust_body_z_feedback": {"type": "number"},
                    "thrust_body_z_sp": {"type": "number"},
                    "thrust_bias": {"type": "number"},
                    "hte_valid": {"type": "boolean"},
                    "hte_active": {"type": "boolean"},
                },
                "required": [
                    "timestamp",
                    "thrust_axis_specific_force_sp",
                    "thrust_axis_specific_force",
                    "hover_thrust_estimate",
                    "rates_sp",
                    "thrust_body_z_ff",
                    "thrust_body_z_feedback",
                    "thrust_body_z_sp",
                    "thrust_bias",
                    "hte_valid",
                    "hte_active",
                ],
            }
        ).encode("utf-8")

    def encode_json(self, data: bytes) -> bytes:
        msg = self.decode(data)
        payload = asdict(msg)
        payload["rates_sp"] = list(msg.rates_sp)
        return json.dumps(payload).encode("utf-8")
