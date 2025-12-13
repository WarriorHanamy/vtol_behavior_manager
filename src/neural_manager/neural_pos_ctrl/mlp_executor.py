import onnxruntime as ort
import numpy as np

class MLPPolicyExecutor:
    def __init__(self, onnx_path, providers=None):
        """
        MLP Policy Executor for pure MLP models (no hidden state)

        Args:
            onnx_path: 模型路径
            providers: 执行提供者列表，默认优先使用 CUDA
        """
        if providers is None:
            # 优先尝试 CUDA，如果不可用则回退到 CPU
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

        try:
            self.session = ort.InferenceSession(onnx_path, providers=providers)
        except Exception as e:
            print(f"Error loading ONNX model with providers {providers}: {e}")
            # 如果 CUDA 失败，尝试仅使用 CPU
            print("Falling back to CPUExecutionProvider...")
            self.session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])

        # 打印当前实际使用的设备，方便调试
        print(f"MLP Policy loaded on: {self.session.get_providers()[0]}")

    def reset(self):
        """重置状态 (MLP无状态，所以为空操作)"""
        pass

    def __call__(self, obs):
        """
        执行推理

        Args:
            obs: 观测值，可以是 (obs_dim,) 或 (batch_size, obs_dim)

        Returns:
            action: 动作值，形状为 (action_dim,) 或 (batch_size, action_dim)
        """
        if obs.ndim == 1:
            obs = obs[None, :] # 增加 batch 维度 -> (1, obs_dim)

        obs = obs.astype(np.float32)

        # MLP模型只需要观测输入，无隐藏状态
        input_name = self.session.get_inputs()[0].name
        inputs = {input_name: obs}

        # 运行推理
        action = self.session.run(None, inputs)[0]

        # 如果输出是 (1, action_dim)，squeeze 掉 batch 维度
        if action.shape[0] == 1:
            return action.squeeze(0)
        return action

# --- 使用示例 ---

if __name__ == "__main__":
    # 确保你安装了 onnxruntime-gpu
    # pip install onnxruntime-gpu

    # 显式指定 Provider，或者留空使用默认（默认即为 CUDA 优先）
    my_providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

    policy = MLPPolicyExecutor(
        "mlp_model.onnx",
        providers=my_providers
    )

    # 模拟一个观察值
    dummy_obs = np.random.randn(20)  # MLP模型通常输入维度较小

    # 推理
    act = policy(dummy_obs)
    print("Action shape:", act.shape)