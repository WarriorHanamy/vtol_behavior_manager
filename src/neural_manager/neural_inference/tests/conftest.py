"""
pytest configuration and fixtures for neural_pos_ctrl tests.

This module provides common fixtures for:
- ROS2 component mocking
- ONNX/TensorRT model mocking
- Environment detection and skipping
- Test data generation
"""

import os
import sys
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import Mock, MagicMock
from typing import Generator, Optional

# Add parent directory to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Path Fixtures
# =============================================================================

@pytest.fixture
def project_root() -> Path:
    """Get the project root directory."""
    return PROJECT_ROOT


@pytest.fixture
def fixtures_dir(project_root: Path) -> Path:
    """Get the test fixtures directory."""
    return project_root / "tests" / "fixtures"


@pytest.fixture
def models_dir(project_root: Path) -> Path:
    """Get the models directory."""
    return project_root / "models"


# =============================================================================
# ROS2 Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_logger():
    """Mock ROS2 logger with call tracking."""
    logger = Mock()
    logger.info_calls = []
    logger.warning_calls = []
    logger.error_calls = []

    def info(msg):
        logger.info_calls.append(msg)

    def warning(msg):
        logger.warning_calls.append(msg)

    def error(msg):
        logger.error_calls.append(msg)

    logger.info.side_effect = info
    logger.warning.side_effect = warning
    logger.error.side_effect = error

    return logger


@pytest.fixture
def mock_ros2_node(mock_logger):
    """
    Mock ROS2 node with logger and publisher/subscriber mocks.

    Usage:
        node = mock_ros2_node()
        publisher = node.create_publisher(msg_type, "topic", 10)
    """
    node = Mock()
    node.get_logger.return_value = mock_logger

    # Track created publishers and subscribers
    node._publishers = {}
    node._subscribers = {}

    def create_publisher(msg_type, topic, qos_profile):
        publisher = Mock()
        publisher.topic = topic
        publisher.msg_type = msg_type
        publisher.published = []

        def publish(msg):
            publisher.published.append(msg)

        publisher.publish.side_effect = publish
        node._publishers[topic] = publisher
        return publisher

    def create_subscription(msg_type, topic, callback, qos_profile):
        subscription = Mock()
        subscription.topic = topic
        subscription.msg_type = msg_type
        subscription.callback = callback
        node._subscribers[topic] = subscription
        return subscription

    node.create_publisher.side_effect = create_publisher
    node.create_subscription.side_effect = create_subscription

    return node


@pytest.fixture
def mock_vehicle_odometry():
    """Create mock VehicleOdometry message."""
    msg = Mock()
    msg.timestamp = 1234567890
    msg.position = np.array([1.0, 2.0, -3.0], dtype=np.float32)
    msg.q = np.array([0.9, 0.1, 0.2, 0.3], dtype=np.float32)  # [w, x, y, z]
    msg.velocity = np.array([0.5, 0.3, -0.2], dtype=np.float32)
    msg.angular_velocity = np.array([0.1, 0.05, 0.02], dtype=np.float32)
    msg.position_variance = np.array([0.01, 0.01, 0.01], dtype=np.float32)
    msg.orientation_variance = np.array([0.001, 0.001, 0.001], dtype=np.float32)
    return msg


@pytest.fixture
def mock_rates_setpoint():
    """Create mock VehicleRatesSetpoint message."""
    msg = Mock()
    msg.timestamp = 1234567890
    msg.thrust_body = np.array([0.0, 0.0, 15.0], dtype=np.float32)
    msg.roll = 0.1
    msg.pitch = -0.05
    msg.yaw = 0.2
    return msg


# =============================================================================
# ONNX Model Fixtures
# =============================================================================

@pytest.fixture
def sample_onnx_model(tmp_path):
    """
    Create a minimal valid ONNX model for testing.

    Returns a simple linear model: y = Wx + b
    """
    try:
        import onnx
        from onnx import helper, TensorProto
    except ImportError:
        pytest.skip("onnx not available")

    # Create simple linear model
    input_tensor = helper.make_tensor_value_info('input', TensorProto.FLOAT, [1, 20])
    output_tensor = helper.make_tensor_value_info('output', TensorProto.FLOAT, [1, 4])

    W_init = helper.make_tensor('W', TensorProto.FLOAT, [20, 4],
                                np.random.randn(20, 4).flatten().tolist())
    b_init = helper.make_tensor('b', TensorProto.FLOAT, [4], np.zeros(4).tolist())

    matmul_node = helper.make_node('MatMul', ['input', 'W'], ['matmul_out'])
    add_node = helper.make_node('Add', ['matmul_out', 'b'], ['output'])

    graph = helper.make_graph(
        [matmul_node, add_node],
        'test_model',
        [input_tensor],
        [output_tensor],
        [W_init, b_init]
    )
    model = helper.make_model(graph)
    model.opset_import[0].version = 14

    model_path = tmp_path / "test_model.onnx"
    onnx.save(model, str(model_path))
    return model_path


@pytest.fixture
def sample_gru_onnx_model(tmp_path):
    """
    Create a minimal GRU ONNX model for testing.

    Returns a GRU model with hidden state input/output.
    """
    try:
        import onnx
        from onnx import helper, TensorProto
    except ImportError:
        pytest.skip("onnx not available")

    # Input observation
    input_obs = helper.make_tensor_value_info('obs', TensorProto.FLOAT, [1, 20])

    # Hidden state input
    input_h = helper.make_tensor_value_info('h_state', TensorProto.FLOAT, [1, 1, 64])

    # Output action
    output_action = helper.make_tensor_value_info('action', TensorProto.FLOAT, [1, 4])

    # Hidden state output
    output_h = helper.make_tensor_value_info('h_out', TensorProto.FLOAT, [1, 1, 64])

    # Simple GRU cell (simplified for testing)
    gru_node = helper.make_node(
        'GRU',
        ['obs', 'h_state'],
        ['action', 'h_out'],
        hidden_size=64
    )

    graph = helper.make_graph(
        [gru_node],
        'test_gru_model',
        [input_obs, input_h],
        [output_action, output_h]
    )
    model = helper.make_model(graph)
    model.opset_import[0].version = 14

    model_path = tmp_path / "test_gru_model.onnx"
    onnx.save(model, str(model_path))
    return model_path


# =============================================================================
# TensorRT Fixtures
# =============================================================================

@pytest.fixture
def requires_tensorrt():
    """Skip test if TensorRT not available."""
    try:
        import tensorrt as trt
    except ImportError:
        pytest.skip("TensorRT not available")


@pytest.fixture
def requires_gpu():
    """Skip test if GPU/CUDA not available."""
    try:
        import onnxruntime as ort
        if 'CUDAExecutionProvider' not in ort.get_available_providers():
            pytest.skip("CUDA not available")
    except ImportError:
        pytest.skip("onnxruntime not available")


# =============================================================================
# Observation Fixtures
# =============================================================================

@pytest.fixture
def sample_observation():
    """Create a sample observation vector."""
    return np.array([
        0.0, 0.0, -3.0,  # position [N, E, D]
        0.0, 0.0, 0.0,  # velocity [N, E, D]
        1.0, 0.0, 0.0, 0.0,  # quaternion [w, x, y, z]
        0.0, 0.0, 0.0,  # angular velocity [roll, pitch, yaw]
        1.0, 1.0, -5.0,  # target position [N, E, D]
        1.57,  # target yaw
        0.5, 0.5  # stick commands [horizontal, vertical]
    ], dtype=np.float32)


@pytest.fixture
def sample_action():
    """Create a sample action vector."""
    return np.array([
        0.1,  # thrust
        0.05,  # roll rate
        -0.02,  # pitch rate
        0.15  # yaw rate
    ], dtype=np.float32)


# =============================================================================
# Configuration Fixtures
# =============================================================================

@pytest.fixture
def sample_config():
    """Create a sample configuration dictionary."""
    return {
        "model": {
            "path": "/tmp/test_model.onnx",
            "actor_type": "mlp",
            "hidden_dim": 64,
            "num_layers": 1,
            "inference": {
                "providers": ["CUDAExecutionProvider", "CPUExecutionProvider"],
                "validate_shapes": True
            }
        },
        "control": {
            "update_rate": 100.0,
            "max_acc": 19.62,
            "max_roll_pitch_rate": 3.0,
            "max_yaw_rate": 1.0
        }
    }


# =============================================================================
# Performance Fixtures
# =============================================================================

@pytest.fixture
def benchmark_iterations():
    """Number of iterations for benchmark tests."""
    return 100


@pytest.fixture
def warmup_iterations():
    """Number of warmup iterations before benchmarking."""
    return 10


# =============================================================================
# Environment Detection Fixtures
# =============================================================================

@pytest.fixture
def in_ros2_environment():
    """Check if running in ROS2 environment."""
    return "/opt/ros/humble" in os.environ.get("AMENT_PREFIX_PATH", "")


@pytest.fixture
def in_tensorrt_venv():
    """Check if running in TensorRT virtual environment."""
    try:
        import tensorrt as trt
        return True
    except ImportError:
        return False
