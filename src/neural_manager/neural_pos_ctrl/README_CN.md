# Neural Position Control 推理节点详细文档

## 📋 概述

这是一个基于神经网络的位置控制推理节点，用于PX4无人机的实时控制。该系统使用在Isaac Sim中训练的ONNX模型，通过ROS2接收飞行器状态信息并输出控制指令。

**主要特点：**
- 🧩 模块化组件架构，易于测试和维护
- 🔄 支持GRU和MLP两种神经网络架构
- ⚡ 高性能实时推理（< 10ms）
- 🎯 端到端的数据处理流水线
- 📊 详细的性能监控和日志

---

## 🏗️ 系统架构

### 整体流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                    Neural Control Node                           │
│                    (neural_infer.py)                             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Inference Pipeline                              │
│              (inference_pipeline.py)                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  1. Odometry Callback                                    │   │
│  │  2. Observation Processing                               │   │
│  │  3. History Management (MLP only)                        │   │
│  │  4. Neural Inference                                     │   │
│  │  5. Action Post-Processing                               │   │
│  │  6. Command Publishing                                   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
           │              │              │              │
           ▼              ▼              ▼              ▼
    ┌──────────┐  ┌─────────────┐  ┌─────────┐  ┌──────────────┐
    │Observation│  │Policy Actor │  │ Action  │  │Communicator  │
    │Processor  │  │(GRU/MLP)    │  │Post-Proc│  │              │
    └──────────┘  └─────────────┘  └─────────┘  └──────────────┘
         │              │              │              │
         └──────────────┴──────────────┴──────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │History      │
                    │Buffer (MLP) │
                    └─────────────┘
```

---

## 🔧 核心组件详解

### 1. **主节点 (neural_infer.py)**

**职责：** ROS2节点入口，组件初始化和生命周期管理

**关键功能：**
- 使用Hydra加载YAML配置文件
- 创建并初始化所有组件
- 管理节点生命周期（启动、运行、关闭）

**配置文件：** `conf/pos_ctrl_config.yaml`

```python
# 主要类
class NeuralControlNode(rclpy.node.Node):
    - __init__(cfg: DictConfig)          # 初始化节点
    - init_components() -> bool          # 初始化所有组件
    - _create_policy_actor()             # 创建策略执行器
    - shutdown_pipeline()                # 关闭管道
```

---

### 2. **推理管道 (inference_pipeline.py)**

**职责：** 协调整个推理流程，从接收数据到发送控制指令

**数据流：**
```
VehicleOdometry → Observation → History (MLP) → Inference → Action → Command
```

**关键方法：**
```python
class NeuralInferencePipeline:
    - initialize()                        # 初始化管道
    - _odometry_callback(msg)            # 里程计消息回调（核心）
    - run_inference(obs)                 # 执行神经网络推理
    - _is_ready_for_processing()         # 检查是否准备就绪
    - get_all_components_info()          # 获取所有组件信息
    - shutdown()                         # 关闭管道
```

**核心流程（_odometry_callback）：**
```python
1. 检查管道状态（是否激活、模型是否加载）
2. 处理里程计消息 → 观测向量 (16维)
3. 添加上一帧动作 → 完整观测 (20维 = 16 + 4)
4. [MLP专用] 更新历史缓冲区
5. 执行神经网络推理 → 原始动作 (4维)
6. 后处理动作 → PX4控制消息
7. 发布控制指令
```

---

### 3. **观测处理器 (observation_processor.py)**

**职责：** 将PX4里程计数据转换为神经网络输入格式

**坐标系转换：**
- **PX4坐标系：** NED (North-East-Down)，四元数为被动旋转
- **Isaac坐标系：** FLU (Forward-Left-Up)，四元数为主动旋转

**观测向量构成（16维）：**
```python
[0:3]   → 目标位置相对误差 (FLU坐标系)
[3:6]   → 当前线速度 (FLU坐标系)
[6:9]   → 当前角速度 (FLU坐标系)
[9:12]  → 重力方向 (机体坐标系)
[12:15] → 角度误差 (航向角差异)
[15]    → 航向角误差标量
```

**关键方法：**
```python
class ObservationProcessor:
    - process_vehicle_odometry(msg)      # 处理里程计消息
    - _extract_observation_from_message() # 提取观测数据
    - _apply_input_saturation()          # 输入饱和限制
    - print_observation()                # 调试输出
```

**数学转换示例：**
```python
# 位置误差 (NED → FLU)
pos_error_ned = target_pos_ned - current_pos_ned
pos_error_flu = frd_flu_rotate(pos_error_ned)

# 四元数转换 (被动 → 主动)
quat_flu = quat_pas_rot(quat_ned)

# 角速度转换 (NED → FLU)
angular_vel_flu = frd_flu_rotate(angular_vel_ned)
```

---

### 4. **策略执行器 (actors.py)**

**职责：** 使用ONNX Runtime执行神经网络推理

#### 4.1 基类：BasePolicyActor

**共同功能：**
- ONNX模型加载（支持CUDA/CPU）
- 推理性能统计
- 观测预处理（批次维度处理）

```python
class BasePolicyActor(ABC):
    - __init__(onnx_path, providers, node_logger)
    - reset()                              # 重置状态（抽象方法）
    - __call__(obs)                        # 执行推理（抽象方法）
    - _prepare_observation(obs)            # 预处理观测
    - get_inference_stats()                # 获取性能统计
```

#### 4.2 GRU执行器：GRUPolicyActor

**特点：** 
- 有状态模型（维护隐藏状态）
- 输入：单个观测 `[1, 20]`
- 输出：动作 `[1, 4]`

**推理流程：**
```python
# 输入
input = {
    "obs": [1, 20],           # 当前观测
    "h_state": [num_layers, 1, hidden_dim]  # 上一帧隐藏状态
}

# 推理
action, h_out = session.run(None, input)

# 更新隐藏状态（关键！）
self.h_state = h_out

return action  # [1, 4]
```

**配置参数：**
```yaml
model:
  actor_type: "gru"
  hidden_dim: 64          # 隐藏层维度
  num_layers: 1           # GRU层数
```

#### 4.3 MLP执行器：MLPPolicyActor

**特点：**
- 无状态模型（不需要隐藏状态）
- 输入：单个观测 `[1, 20]` 或历史堆叠 `[1, history_length * 20]`
- 输出：动作 `[1, 4]`

**推理流程：**
```python
# 输入（根据配置）
if history.enabled:
    input = [1, history_length * 20]  # 历史堆叠
else:
    input = [1, 20]                   # 单个观测

# 推理
action = session.run(None, {"input": input})[0]

return action  # [1, 4]
```

**配置参数：**
```yaml
model:
  actor_type: "mlp"
  history:
    enabled: false        # 是否使用历史堆叠
    length: 5             # 历史长度
    obs_dim: 20           # 单个观测维度
```

---

### 5. **动作后处理器 (action_post_processor.py)**

**职责：** 将神经网络原始输出转换为PX4控制指令

**处理流程：**

```python
# 1. 原始动作 (模型输出)
raw_action = [thrust_raw, roll_raw, pitch_raw, yaw_raw]  # 任意范围

# 2. 激活函数 (映射到 [-1, 1])
action = tanh(raw_action)  # 平滑映射

# 3. 动作缩放
thrust = action[0]                              # 保持 [-1, 1]
roll_rate = action[1] * max_roll_pitch_rate     # rad/s
pitch_rate = action[2] * max_roll_pitch_rate    # rad/s
yaw_rate = action[3] * max_yaw_rate             # rad/s

# 4. 坐标转换 (FLU → FRD)
[roll_rate_frd, pitch_rate_frd, yaw_rate_frd] = frd_flu_rotate([roll_rate, pitch_rate, yaw_rate])

# 5. 创建PX4消息
msg = VehicleRatesSetpoint()
msg.roll = roll_rate_frd
msg.pitch = pitch_rate_frd
msg.yaw = yaw_rate_frd
msg.thrust_body = [0.0, 0.0, -thrust]  # 推力方向向下
```

**控制模式：**

1. **rates_throttle（推荐）：** 油门 + 体轴角速率
   - 消息类型：`VehicleRatesSetpoint`
   - 适用于多旋翼
   
2. **rates_acc（实验性）：** 推力加速度 + 体轴角速率
   - 消息类型：`VehicleThrustAccSetpoint`
   - 需要精确的推力模型

**配置参数：**
```yaml
control:
  mode: "rates_throttle"
  max_roll_pitch_rate: 1.0    # rad/s
  max_yaw_rate: 1.0            # rad/s
  thrust_acc: 9.81             # m/s^2 (仅rates_acc模式)
  use_tanh_activation: true    # 使用tanh激活
```

---

### 6. **通信器 (communicator.py)**

**职责：** 管理所有ROS2发布者和订阅者

**订阅的话题：**
```yaml
/fmu/out/vehicle_odometry  → VehicleOdometry (输入)
```

**发布的话题：**
```yaml
/neural/control  → VehicleRatesSetpoint (输出)
```

**QoS配置：**
```python
qos_profile_sensor_data  # 可靠性：Best Effort，适合高频传感器数据
```

**统计信息：**
- 接收消息数量
- 发布消息数量
- 发布速率
- 消息时延

---

### 7. **历史缓冲区 (history_buffer.py)**

**职责：** 为MLP模型维护观测历史（仅在MLP需要时使用）

**数据结构：** 循环缓冲区

```python
# 示例：history_length=5, obs_dim=20
buffer = [
    [obs_t-4],  # 最旧
    [obs_t-3],
    [obs_t-2],
    [obs_t-1],
    [obs_t]     # 最新
]

# 堆叠输出：[obs_t-4, obs_t-3, obs_t-2, obs_t-1, obs_t]
# 维度：(5 * 20) = 100
```

**关键方法：**
```python
class ObservationHistoryBuffer:
    - add_observation(obs)        # 添加新观测
    - get_stacked_history()       # 获取堆叠历史
    - reset()                     # 重置缓冲区
```

**使用场景：**
- MLP模型需要时间序列信息
- 替代GRU的隐藏状态机制

---

## 🔄 完整数据流示例

### 输入数据（PX4 → 节点）

```python
# VehicleOdometry消息
{
    "timestamp": 1234567890,
    "position": [1.0, 2.0, -5.0],          # NED坐标系
    "velocity": [0.5, 0.0, -0.2],          # NED坐标系
    "q": [1.0, 0.0, 0.0, 0.0],             # 四元数 (w, x, y, z)
    "angular_velocity": [0.1, 0.0, 0.05],  # NED坐标系
}
```

### 中间处理

```python
# 1. 观测处理 (16维)
observation = [
    # 位置误差 (FLU)
    -1.0, -2.0, 5.0,
    # 速度 (FLU)
    0.5, 0.0, 0.2,
    # 角速度 (FLU)
    0.1, 0.0, -0.05,
    # 重力方向 (Body)
    0.0, 0.0, -1.0,
    # 角度误差
    0.0, 0.0, 0.1,
    # 航向误差
    0.1
]

# 2. 添加上一帧动作 (20维)
observation_with_action = [
    observation,        # 16维
    last_action        # 4维 [0.5, 0.1, -0.1, 0.05]
]

# 3. 神经网络推理
raw_action = model(observation_with_action)
# 输出: [0.8, 0.2, -0.1, 0.03]

# 4. 动作后处理
processed_action = tanh(raw_action)
# 输出: [0.664, 0.197, -0.099, 0.029]

# 5. 缩放和转换
thrust = 0.664
roll_rate = 0.197 * 1.0 = 0.197 rad/s
pitch_rate = -0.099 * 1.0 = -0.099 rad/s
yaw_rate = 0.029 * 1.0 = 0.029 rad/s
```

### 输出数据（节点 → PX4）

```python
# VehicleRatesSetpoint消息
{
    "timestamp": 1234567891,
    "roll": 0.197,                  # rad/s (FRD)
    "pitch": -0.099,                # rad/s (FRD)
    "yaw": 0.029,                   # rad/s (FRD)
    "thrust_body": [0.0, 0.0, -0.664]  # 归一化推力
}
```

---

## ⚙️ 配置文件详解

### 完整配置示例

```yaml
# conf/pos_ctrl_config.yaml

# ========== 节点配置 ==========
node:
  name: "neural_pos_ctrl_node"
  setpoint_topic: "/neural/control"
  odometry_topic: "/fmu/out/vehicle_odometry"

# ========== 模型配置 ==========
model:
  # 模型路径（支持环境变量）
  path: "${oc.env:INFER_WORKSPACE}/src/neural_manager/neural_pos_ctrl/models/policy_x500.onnx"
  
  # 执行器类型：gru 或 mlp
  actor_type: "mlp"
  
  # GRU参数（仅actor_type=gru时使用）
  hidden_dim: 64
  num_layers: 1
  
  # 历史缓冲区（仅actor_type=mlp时使用）
  history:
    enabled: false      # 是否启用
    length: 5          # 历史长度
    obs_dim: 20        # 观测维度
  
  # 形状验证
  expected_shapes:
    gru:
      input: [1, 20]
      output: [1, 4]
    mlp:
      input: [1, 20]
      output: [1, 4]
  
  # ONNX推理配置
  inference:
    providers: ["CUDAExecutionProvider", "CPUExecutionProvider"]
    validate_shapes: true
    output_clipping:
      enabled: true
      min: -1.0
      max: 1.0

# ========== 控制配置 ==========
control:
  # 控制模式
  mode: "rates_throttle"
  
  # 更新频率
  update_rate: 100.0
  update_period: 0.01
  timeout_ms: 50.0
  
  # 角速率限制
  max_roll_pitch_rate: 1.0    # rad/s
  max_yaw_rate: 1.0           # rad/s
  
  # 推力配置
  thrust_acc: 9.81            # m/s^2
  use_tanh_activation: true
  
  # 输入饱和
  input_saturation:
    enabled: true
    target_position: [-5.0, 5.0]  # 米

# ========== 目标配置 ==========
target:
  position: [0.0, 0.0, -5.0]  # NED坐标系
  yaw: 0.0                     # 弧度

# ========== 调试配置 ==========
debug:
  print_observation: false
  print_control: false
  acc_fixed: false
  enable_debug_timer: true
  debug_timer_period: 5.0
```

---

## 🚀 使用指南

### 1. 环境准备

```bash
# 安装依赖
pip install onnxruntime numpy hydra-core omegaconf

# 如果使用GPU加速
pip install onnxruntime-gpu
```

### 2. 准备模型文件

```bash
# 将ONNX模型放到models目录
cp your_policy.onnx src/neural_manager/neural_pos_ctrl/models/
```

### 3. 配置参数

编辑 `conf/pos_ctrl_config.yaml`：

```yaml
# 1. 设置模型路径
model:
  path: "path/to/your/model.onnx"

# 2. 选择执行器类型
model:
  actor_type: "mlp"  # 或 "gru"

# 3. 设置目标点
target:
  position: [5.0, 0.0, -3.0]  # 目标位置
  yaw: 0.0                     # 目标航向
```

### 4. 运行节点

```bash
# 方法1：直接运行
python3 neural_infer.py

# 方法2：ROS2运行
ros2 run neural_pos_ctrl neural_infer

# 方法3：使用launch文件
ros2 launch neural_executor neural_control.launch.py
```

### 5. 监控运行状态

```bash
# 查看话题
ros2 topic list

# 监听控制输出
ros2 topic echo /neural/control

# 查看节点信息
ros2 node info neural_pos_ctrl_node
```

---

## 📊 性能指标

### 典型性能数据

| 指标 | GRU模型 | MLP模型 |
|------|---------|---------|
| 推理时间 | 2-5 ms | 1-3 ms |
| 控制频率 | 100 Hz | 100 Hz |
| CPU占用 | ~10% | ~8% |
| 内存占用 | ~200 MB | ~150 MB |

### 延迟分析

```
总延迟 = 数据接收 + 观测处理 + 推理 + 后处理 + 发布
        ≈ 1ms    + 0.5ms    + 3ms + 0.5ms  + 1ms
        = 6ms (典型值)
```

---

## 🐛 故障排查

### 常见问题

#### 1. 模型加载失败
```
错误：模型文件不存在
解决：检查模型路径，确保文件存在
```

#### 2. 形状不匹配
```
错误：输入形状不匹配，期望 [1, 20]，实际 [1, 16]
解决：检查观测维度配置，确认是否包含last_action
```

#### 3. 推理速度慢
```
问题：推理时间 > 20ms
解决：
  - 检查是否使用GPU加速
  - 确认CUDA正确安装
  - 尝试使用ONNX优化工具
```

#### 4. 控制不稳定
```
问题：飞行器震荡或发散
解决：
  - 检查坐标系转换是否正确
  - 降低max_roll_pitch_rate
  - 验证目标点设置合理
```

---

## 🔍 调试技巧

### 1. 启用调试输出

```yaml
debug:
  print_observation: true
  print_control: true
```

### 2. 查看组件信息

```python
# 在代码中添加
info = node.get_pipeline_info()
print(info)
```

### 3. 记录推理统计

```python
stats = node._pipeline._policy_actor.get_inference_stats()
print(f"平均推理时间: {stats['average_inference_time']:.2f} ms")
print(f"推理速率: {stats['inference_rate']:.1f} Hz")
```

---

## 📚 相关文档

- [PX4消息定义](https://github.com/PX4/px4_msgs)
- [ONNX Runtime文档](https://onnxruntime.ai/)
- [Hydra配置框架](https://hydra.cc/)
- [Isaac Sim强化学习](https://docs.omniverse.nvidia.com/isaacsim/latest/index.html)

---

## 📝 开发注意事项

### 坐标系约定

| 系统 | 坐标系 | 四元数类型 |
|------|--------|-----------|
| PX4 | NED (North-East-Down) | 被动旋转 |
| Isaac | FLU (Forward-Left-Up) | 主动旋转 |

### 数据单位

| 变量 | 单位 |
|------|------|
| 位置 | 米 (m) |
| 速度 | 米/秒 (m/s) |
| 角速度 | 弧度/秒 (rad/s) |
| 角度 | 弧度 (rad) |
| 时间戳 | 微秒 (μs) |
| 推力 | 归一化 [-1, 1] |

### 代码风格

- 使用类型注解
- 详细的docstring
- 模块化设计
- 错误处理完善

---

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

**联系方式：**
- Email: support@differential-robotics.com
- GitHub: [WarriorHanamy/vtol-interface](https://github.com/WarriorHanamy/vtol-interface)

---

## 📄 许可证

BSD-3-Clause License

Copyright (c) 2025, Differential Robotics
