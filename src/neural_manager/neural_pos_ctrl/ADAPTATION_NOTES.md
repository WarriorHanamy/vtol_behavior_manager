# Neural Position Control Adaptation Notes

## 概述
此文档记录了 vtol_interface neural_pos_ctrl 与 isaac_drone_ctrl 训练环境之间的适配工作。

## 适配日期
2026-01-08

## 观测空间适配

### 原始 vtol_interface 观测顺序 (OLD)
```
索引 0-2:   lin_vel_b_flu (3D) - 机体线速度
索引 3-5:   ang_vel_b_flu (3D) - 机体角速度
索引 6-8:   to_target_pos_b_flu (3D) - 目标位置(机体坐标)
索引 9-11:  gra_dir_b_flu (3D) - 重力投影(机体坐标)
索引 12-13: current_yaw_dir (2D) - 当前yaw方向
索引 14-15: target_yaw_dir (2D) - 目标yaw方向
索引 16-19: last_action (4D) - 上一次动作
总计: 20维
```

### 适配后的观测顺序 (NEW - 匹配 drone_pos_ctrl_env_cfg.py)
```
索引 0-2:   lin_vel_b_flu (3D) - 机体线速度
索引 3-5:   gra_dir_b_flu (3D) - 重力投影(机体坐标) [移到前面]
索引 6-8:   ang_vel_b_flu (3D) - 机体角速度 [移到后面]
索引 9-10:  current_yaw_dir (2D) - 当前yaw方向
索引 11-13: to_target_pos_b_flu (3D) - 目标位置(机体坐标) [移到后面]
索引 14-15: target_yaw_dir (2D) - 目标yaw方向
索引 16-19: last_action (4D) - 上一次动作
总计: 20维
```

### 训练环境观测定义 (drone_pos_ctrl_env_cfg.py PolicyCfg)
```python
class PolicyCfg(ObsGroup):
    lin_vel = ObsTerm(func=mdp.root_lin_vel_b)                    # 3D
    projed_gravity_b = ObsTerm(func=mdp.projected_gravity_b)      # 3D
    ang_vel = ObsTerm(func=mdp.root_ang_vel_b)                    # 3D
    current_yaw_direction = ObsTerm(func=mdp.current_yaw_direction_w)  # 2D
    target_pos_b = ObsTerm(                                       # 3D
        func=mdp.target_distance_vector_b,
        params={"command_name": "position_command"}
    )
    target_yaw_w = ObsTerm(                                       # 2D
        func=mdp.target_yaw_w,
        params={"command_name": "position_command"}
    )
    actions = ObsTerm(func=mdp.last_action)                       # 4D
```

## 关键修改

### 1. observation_processor.py
**文件路径**: `/workspace/isaac/vtol-interface/src/neural_manager/neural_pos_ctrl/infer_utils/observation_processor.py`

#### 修改1: 观测向量组装顺序 (line ~194-210)
```python
# 修改前
observation = np.concatenate([
    lin_vel_b_flu,      # 0-2
    ang_vel_b_flu,      # 3-5
    to_target_pos_b_flu,# 6-8
    gra_dir_b_flu,      # 9-11
    current_yaw_dir,    # 12-13
    target_yaw_dir,     # 14-15
], dtype=np.float32)

# 修改后 (匹配训练环境顺序)
observation = np.concatenate([
    lin_vel_b_flu,      # 0-2
    gra_dir_b_flu,      # 3-5  [提前]
    ang_vel_b_flu,      # 6-8  [延后]
    current_yaw_dir,    # 9-10
    to_target_pos_b_flu,# 11-13 [延后]
    target_yaw_dir,     # 14-15
], dtype=np.float32)
```

#### 修改2: 输入饱和索引 (line ~230)
```python
# 修改前
observation[6:9] = np.clip(observation[6:9], ...)  # target_pos旧位置

# 修改后
observation[11:14] = np.clip(observation[11:14], ...)  # target_pos新位置
```

#### 修改3: 打印函数索引 (line ~254-263)
```python
# 修改前
lin_vel_b = observation[0:3]
ang_vel_b = observation[3:6]
to_target_pos_b = observation[6:9]
gra_dir_b = observation[9:12]
current_yaw_dir = observation[12:14]
target_yaw_dir = observation[14:16]

# 修改后
lin_vel_b = observation[0:3]
gra_dir_b = observation[3:6]
ang_vel_b = observation[6:9]
current_yaw_dir = observation[9:11]
to_target_pos_b = observation[11:14]
target_yaw_dir = observation[14:16]
```

## 动作空间 (无需修改)

动作空间保持不变，都是4维：
```
[0]: throttle/thrust (油门/推力)
[1]: roll_rate (滚转角速率)
[2]: pitch_rate (俯仰角速率)
[3]: yaw_rate (偏航角速率)
```

## 动作处理 (重要修改)

### 训练环境 (isaac_drone_ctrl)
使用 **tanh 激活函数**而不是硬截断 (clamp)：
```python
# actions.py process_actions()
raw_actions = mlp_output  # 原始 MLP 输出
clamped_actions = torch.tanh(raw_actions)  # 使用 tanh 映射到 [-1, 1]
```

**优点**:
- 梯度更平滑，训练更稳定
- 自然地将输出限制在 [-1, 1] 范围
- 没有硬边界，避免梯度消失

### 部署环境 (vtol_interface)
**已适配**: 使用相同的 tanh 激活函数

```python
# action_post_processor.py
if self._use_tanh_activation:
    action = np.tanh(raw_action)  # 匹配训练环境
```

**配置**:
```yaml
# conf/pos_ctrl_config.yaml
control:
  action_processing:
    use_tanh_activation: true  # 默认启用
    enable_action_clipping: false  # 不使用硬截断
```

## 坐标系统

### 训练环境 (IsaacLab)
- 世界坐标系: ENU (East-North-Up)
- 机体坐标系: FLU (Forward-Left-Up)

### 部署环境 (PX4)
- 世界坐标系: NED (North-East-Down)
- 机体坐标系: FRD (Forward-Right-Down)

### 坐标转换
已在 `observation_processor.py` 和 `action_post_processor.py` 中实现：
- 观测: NED → FLU 转换
- 动作: FLU → FRD 转换

## 验证清单

- [x] 观测向量组装顺序匹配训练环境
- [x] 观测维度正确 (16维 obs + 4维 last_action = 20维)
- [x] 输入饱和索引更新
- [x] 打印函数索引更新
- [x] 动作处理使用 tanh 激活函数（匹配训练环境）
- [x] 坐标系转换正确
- [ ] 实际测试验证 (待完成)

## 配置文件

### 模型配置 (pos_ctrl_config.yaml)
```yaml
model:
  actor_type: "mlp"  # 或 "gru"
  history:
    enabled: true
    length: 5
    obs_dim: 20  # 16 obs + 4 last_action
  expected_shapes:
    mlp:
      input: [1, 100]  # 5 * 20
      output: [1, 4]
```

## 使用说明

1. **训练模型**: 使用 `isaac_drone_ctrl/tasks/drone_racer/drone_pos_ctrl_env_cfg.py`
2. **导出ONNX**: 确保观测顺序与 PolicyCfg 一致
3. **部署**: 将ONNX模型放入 `vtol-interface/src/neural_manager/neural_pos_ctrl/models/`
4. **配置**: 更新 `conf/pos_ctrl_config.yaml` 中的目标位置和参数
5. **运行**: `ros2 run neural_manager neural_pos_ctrl`

## 注意事项

1. **观测顺序至关重要**: 必须与训练时完全一致，否则模型无法正确工作
2. **last_action历史**: 由 `history_buffer.py` 或 `inference_pipeline.py` 自动管理
3. **坐标系转换**: 已在代码中自动处理，无需手动干预
4. **输入饱和**: 默认启用，可在配置文件中调整或关闭

## 相关文件

- 训练环境配置: `isaac_drone_ctrl/tasks/drone_racer/drone_pos_ctrl_env_cfg.py`
- 观测处理器: `vtol-interface/src/neural_manager/neural_pos_ctrl/infer_utils/observation_processor.py`
- 动作处理器: `vtol-interface/src/neural_manager/neural_pos_ctrl/infer_utils/action_post_processor.py`
- 配置文件: `vtol-interface/src/neural_manager/neural_pos_ctrl/conf/pos_ctrl_config.yaml`

## 变更历史

- 2026-01-08: 初始适配，调整观测向量顺序以匹配 drone_pos_ctrl_env_cfg.py
