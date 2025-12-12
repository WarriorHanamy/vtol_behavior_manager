import onnxruntime as ort
import numpy as np

class GRUPolicyExecutor:
    def __init__(self, onnx_path, hidden_dim=64, num_layers=1, providers=None):
        """
        Args:
            onnx_path: 模型路径
            hidden_dim: GRU 隐藏层维度
            num_layers: GRU 层数
            providers: 执行提供者列表，默认优先使用 CUDA
        """
        if providers is None:
            # 优先尝试 CUDA，如果不可用则回退到 CPU
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        
        # 【修改点】在此处传入 providers
        try:
            self.session = ort.InferenceSession(onnx_path, providers=providers)
        except Exception as e:
            print(f"Error loading ONNX model with providers {providers}: {e}")
            # 如果 CUDA 失败，尝试仅使用 CPU
            print("Falling back to CPUExecutionProvider...")
            self.session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])

        # 打印当前实际使用的设备，方便调试
        print(f"Policy loaded on: {self.session.get_providers()[0]}")

        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        # 初始化隐藏状态
        self.h_state = np.zeros((self.num_layers, 1, self.hidden_dim), dtype=np.float32)

    def reset(self):
        """重置隐藏状态"""
        self.h_state = np.zeros((self.num_layers, 1, self.hidden_dim), dtype=np.float32)

    def __call__(self, obs):
        """
        执行推理
        """
        if obs.ndim == 1:
            obs = obs[None, :] # 增加 batch 维度 -> (1, obs_dim)
        
        obs = obs.astype(np.float32)

        inputs = {
            self.session.get_inputs()[0].name: obs,
            self.session.get_inputs()[1].name: self.h_state
        }
        
        # 运行推理
        action, h_out = self.session.run(None, inputs)

        # 【关键步骤】自动更新隐藏状态，供下一帧使用
        self.h_state = h_out

        # 如果输出是 (1, action_dim)，通常 squeeze 掉 batch 维度返回 (action_dim,)
        # 方便直接传给 gym env，视具体需求而定
        return action.squeeze(0)

# --- 使用示例 ---

if __name__ == "__main__":
    # 确保你安装了 onnxruntime-gpu
    # pip install onnxruntime-gpu
    
    # 显式指定 Provider，或者留空使用默认（默认即为 CUDA 优先）
    my_providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    
    policy = GRUPolicyExecutor(
        "model.onnx", 
        hidden_dim=128, 
        providers=my_providers
    )
    
    policy.reset()
    
    # 模拟一个观察值
    dummy_obs = np.random.randn(48) 
    
    # 推理
    act = policy(dummy_obs)
    print("Action shape:", act.shape)