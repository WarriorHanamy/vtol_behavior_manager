# vtol_interface 与 isaac_drone_ctrl 适配完成报告

## 适配概述

已成功将 vtol_interface 的 `neural_pos_ctrl` 模块适配到 `isaac_drone_ctrl` 的 `drone_pos_ctrl_env_cfg.py` 训练环境。

**适配日期**: 2026-01-08

## 主要问题

原始 vtol_interface 的观测向量顺序与训练环境不匹配，导致以下问题：
- 神经网络无法正确解释输入数据
- 模型性能下降或完全失效
- sim2sim/sim2real 测试失败

## 解决方案

### 1. 观测向量顺序重排

将 vtol_interface 的观测组装顺序调整为与训练环境完全一致：

| 索引 | 组件 | 维度 | 说明 |
|------|------|------|------|
| 0-2 | lin_vel | 3D | 机体线速度 [vx, vy, vz] |
| 3-5 | projected_gravity | 3D | 重力投影 [gx, gy, gz] |
| 6-8 | ang_vel | 3D | 机体角速度 [wx, wy, wz] |
| 9-10 | current_yaw_dir | 2D | 当前yaw方向 [cos, sin] |
| 11-13 | target_pos_b | 3D | 目标位置(机体) [dx, dy, dz] |
| 14-15 | target_yaw_w | 2D | 目标yaw方向 [cos, sin] |
| 16-19 | last_action | 4D | 上一次动作 [throttle, roll_r, pitch_r, yaw_r] |

**总计**: 20维

### 2. 修改的文件

#### `/workspace/isaac/vtol-interface/src/neural_manager/neural_pos_ctrl/infer_utils/observation_processor.py`

**修改内容**:
1. **观测组装顺序** (line ~194-210): 重新排列 `np.concatenate()` 中各组件的顺序
2. **输入饱和索引** (line ~232): 将 target_pos_b 的索引从 `6:9` 改为 `11:14`
3. **打印函数索引** (line ~254-263): 更新所有观测组件的提取索引

#### `/workspace/isaac/vtol-interface/src/neural_manager/neural_pos_ctrl/infer_utils/action_post_processor.py`

**修改内容**:
1. **添加 tanh 激活** (line ~30-65): 
   - 新增 `use_tanh_activation` 参数（默认 True）
   - `enable_action_clipping` 改为可选（默认 False，已弃用）
2. **动作处理逻辑** (line ~95-115): 使用 `np.tanh()` 而不是 `np.clip()`
3. **显示和验证函数**: 同步更新以支持 tanh 激活

#### `/workspace/isaac/vtol-interface/src/neural_manager/neural_pos_ctrl/neural_infer.py`

**修改内容**:
- 更新 ActionPostProcessor 初始化参数，使用新的配置路径
- 从 `control.action_processing` 读取 `use_tanh_activation` 和 `enable_action_clipping`

#### `/workspace/isaac/vtol-interface/src/neural_manager/neural_pos_ctrl/conf/pos_ctrl_config.yaml`

**修改内容**:
- 新增 `control.action_processing` 配置节
- 设置 `use_tanh_activation: true` (默认)
- 设置 `enable_action_clipping: false` (已弃用)

### 3. 验证测试

创建了测试脚本 `test_observation_adaptation.py` 验证适配正确性：

```bash
cd /workspace/isaac/vtol-interface/src/neural_manager/neural_pos_ctrl
python3 test_observation_adaptation.py
```

**测试结果**: ✅ 所有测试通过

- 观测向量一致性: ✓
- 各组件索引正确: ✓
- 输入饱和索引正确: ✓

### 4. 文档

创建了详细的适配文档 `ADAPTATION_NOTES.md`，包含：
- 观测空间详细说明
- 修改历史
- 使用指南
- 注意事项

## 使用流程

### 1. 训练模型

使用 isaac_drone_ctrl 训练环境：

```bash
cd /workspace/isaac/isaac_drone_ctrl
python scripts/rsl_rl/train.py --task=Isaac-Drone-Racer-Position-Control-v0
```

### 2. 导出 ONNX 模型

确保导出时观测顺序与 `drone_pos_ctrl_env_cfg.py` 的 `PolicyCfg` 一致。

### 3. 部署到 PX4

```bash
# 1. 复制模型到 vtol_interface
cp model.onnx /workspace/isaac/vtol-interface/src/neural_manager/neural_pos_ctrl/models/policy_latest.onnx

# 2. 配置目标位置 (编辑 conf/pos_ctrl_config.yaml)
target:
  position: [0.0, 0.0, -5.0]  # NED coordinates
  yaw: 0.0  # radians

# 3. 运行神经网络控制器
ros2 run neural_manager neural_pos_ctrl
```

### 4. Sim2Sim 测试 (Gazebo)

```bash
# 终端1: 启动 PX4 SITL + Gazebo
cd /workspace/isaac/PX4-Autopilot
make px4_sitl gz_x500

# 终端2: 启动神经控制器
ros2 run neural_manager neural_pos_ctrl
```

### 5. Sim2Real 测试 (真实硬件)

```bash
# 连接到真实无人机后
ros2 run neural_manager neural_pos_ctrl
```

## 关键注意事项

### ⚠️ 观测顺序至关重要

观测向量的顺序必须与训练时**完全一致**，任何差异都会导致模型失效。

### ⚠️ 动作处理使用 tanh

**训练环境**使用 `torch.tanh(actions)` 而不是 `clamp()`：
- ✅ **优点**: 梯度平滑，训练稳定，自然边界
- ❌ **错误做法**: 使用硬截断 `np.clip()` 会导致不匹配

**部署环境**必须使用相同的 `np.tanh()`：
```python
# 正确
action = np.tanh(raw_action)  # 匹配训练环境

# 错误 (已弃用)
action = np.clip(raw_action, -1.0, 1.0)  # 不匹配训练环境
```

### 坐标系转换

代码已自动处理以下坐标系转换：
- **观测**: PX4 NED/FRD → IsaacLab FLU
- **动作**: IsaacLab FLU → PX4 FRD

### 配置参数

确保以下参数匹配：

**训练环境** (`drone_pos_ctrl_env_cfg.py`):
- `max_body_rate`: (3.0, 3.0, 1.0) rad/s
- `throttle_limits`: (0.1, 1.0)

**部署环境** (`conf/pos_ctrl_config.yaml`):
- `max_roll_pitch_rate`: 3.0 rad/s
- `max_yaw_rate`: 1.0 rad/s
- `thrust_acc`: 9.8 m/s²

## 测试检查清单

- [x] 观测向量组装顺序匹配训练环境
- [x] 观测维度正确 (20维)
- [x] 输入饱和索引正确
- [x] 打印函数索引正确
- [x] 动作处理使用 tanh 激活函数
- [x] 坐标系转换正确
- [x] 单元测试通过
- [ ] Sim2Sim 测试 (待完成)
- [ ] Sim2Real 测试 (待完成)

## 相关文件

### 训练环境
- `isaac_drone_ctrl/tasks/drone_racer/drone_pos_ctrl_env_cfg.py` - 环境配置
- `isaac_drone_ctrl/tasks/drone_racer/mdp/observations.py` - 观测函数
- `isaac_drone_ctrl/tasks/drone_racer/mdp/actions.py` - 动作处理

### 部署环境
- `vtol-interface/src/neural_manager/neural_pos_ctrl/infer_utils/observation_processor.py` - 观测处理
- `vtol-interface/src/neural_manager/neural_pos_ctrl/infer_utils/action_post_processor.py` - 动作处理
- `vtol-interface/src/neural_manager/neural_pos_ctrl/conf/pos_ctrl_config.yaml` - 配置文件

### 文档
- `vtol-interface/src/neural_manager/neural_pos_ctrl/ADAPTATION_NOTES.md` - 详细适配说明
- `vtol-interface/src/neural_manager/neural_pos_ctrl/test_observation_adaptation.py` - 验证脚本

## 下一步

1. ✅ **完成适配** - 观测向量顺序已匹配
2. ⏭️ **训练模型** - 使用 drone_pos_ctrl_env_cfg.py 训练
3. ⏭️ **导出ONNX** - 导出训练好的模型
4. ⏭️ **Sim2Sim测试** - 在 Gazebo 中验证
5. ⏭️ **Sim2Real测试** - 部署到真实硬件

## 技术细节

### 物理参数 (X500)

已同步更新 isaac_drone_ctrl 的 X500 配置以匹配 PX4 Gazebo 模型：

```python
# X500PhysicsConfig (x500_config.py)
mass: 2.0 kg
ixx: 0.021667 kg·m²
iyy: 0.021667 kg·m²
izz: 0.040000 kg·m²
arm_length: 0.246 m  # 对角距离
moment_constant: 0.016 N·m/N
```

### 控制器参数 (PID)

```python
# X500RateControllerConfig
rate_p_gains: (1.5, 1.5, 1.5)
rate_i_gains: (0.2, 0.2, 0.2)
rate_d_gains: (0.003, 0.003, 0.002)
angular_accel_cutoff_freq_hz: 50.0
```

## 结论

✅ **适配完成且验证通过**

vtol_interface 的 neural_pos_ctrl 模块现已与 isaac_drone_ctrl 的训练环境完全兼容，可以进行模型训练和部署测试。

---

**作者**: AI Assistant  
**日期**: 2026-01-08  
**版本**: 1.0
