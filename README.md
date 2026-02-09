<div align="center">

# PX4-ROS2-Bridge

**Bridge between PX4-Autopilot and ROS 2**

[![ROS 2](https://img.shields.io/badge/ROS%202-Humble-blue)](https://docs.ros.org/en/humble/)
[![PX4](https://img.shields.io/badge/PX4-Autopilot-orange)](https://px4.io/)
[![License](https://img.shields.io/badge/License-BSD--3-green.svg)](LICENSE)

</div>


## 🎯 快速开始
### 📥 克隆仓库

```bash
git clone --recursive https://github.com/Arclunar/PX4-ROS2-Bridge.git --depth 1
```
### 配置px4_msgs
```bash
just config-px4msg
```

### Docker 部署 PX4-Gazebo-harmonic

#### 1. 构建 Docker 镜像

**方式 1: 使用 just 命令**
```bash
just build-px4
```

**方式 2: 使用 Docker Compose**
```bash
docker compose build px4
```

> 📚 详细构建指南: [Docker Compose 构建文档](docs/docker-compose-build.md)

#### 2. 测试运行容器启动 PX4-Gazebo-harmonic

```bash
just run-px4
```

### Docker 部署 QGroundControl

#### 1. 构建 Docker 镜像

**方式 1: 使用 just 命令**
```bash
just build-qgc
```

**方式 2: 使用 Docker Compose**
```bash
docker compose build qgc
```

#### 2. 测试运行容器启动 QGroundControl

```bash
just run-qgc
```

### Docker 部署 PX4-ROS2-BRIDGE

#### 1. 构建 Docker 镜像

**方式 1: 使用 just 命令**
```bash
just build-ros2
```

**方式 2: 使用 Docker Compose**
```bash
docker compose build ros2
```

#### 2. 测试运行容器

```bash
just run-ros2
```

#### 3. 编译ros2工作空间
```bash
just build
```

### Docker Compose 快速启动

使用 Docker Compose 可以一次性构建和启动所有服务：

```bash
# 构建所有镜像
docker compose build

# 启动所有服务
docker compose up -d

# 停止所有服务
docker compose down

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f
```

> 📚 详细使用指南: [Docker Compose 构建文档](docs/docker-compose-build.md)




## 📖 使用说明

### 0️⃣ 训练权重和观测对齐

#### 📁 模型文件配置

将训练好的 ONNX 模型文件放置在以下目录：
```
src/neural_manager/neural_pos_ctrl/models/
```

#### ⚙️ 参数配置

修改启动文件中的模型路径：
```bash
src/neural_manager/neural_pos_ctrl/launch/isaac_pos_ctrl_launch.py
```
更新 `model_path` 参数指向你的模型文件。

#### 🔧 观测量对齐

如果观测量设置不同，需要修改观测量对齐函数：
```bash
src/neural_manager/neural_pos_ctrl/isaac_pos_ctrl_neural/pos_ctrl_node.py
```

#### 📊 当前观测量配置

<table>
<tr>
<th width="5%">序号</th>
<th width="30%">观测量名称</th>
<th width="15%">维度</th>
<th width="50%">描述</th>
</tr>
<tr>
<td align="center">1</td>
<td><code>lin_vel</code></td>
<td align="center">3D</td>
<td>线速度 <code>[vx, vy, vz]</code></td>
</tr>
<tr>
<td align="center">2</td>
<td><code>projected_gravity_b</code></td>
<td align="center">3D</td>
<td>投影重力（机体坐标系）<code>[gx, gy, gz]</code></td>
</tr>
<tr>
<td align="center">3</td>
<td><code>ang_vel</code></td>
<td align="center">3D</td>
<td>角速度 <code>[wx, wy, wz]</code></td>
</tr>
<tr>
<td align="center">4</td>
<td><code>current_yaw_direction</code></td>
<td align="center">2D</td>
<td>当前偏航方向 <code>[cos(yaw), sin(yaw)]</code></td>
</tr>
<tr>
<td align="center">5</td>
<td><code>target_pos_b</code></td>
<td align="center">3D</td>
<td>目标位置（机体坐标系）<code>[tx, ty, tz]</code></td>
</tr>
<tr>
<td align="center">6</td>
<td><code>target_yaw</code></td>
<td align="center">2D</td>
<td>目标偏航方向 <code>[cos(yaw_target), sin(yaw_target)]</code></td>
</tr>
<tr>
<td align="center">7</td>
<td><code>actions</code></td>
<td align="center">4D</td>
<td>上一时刻动作 <code>[a1, a2, a3, a4]</code></td>
</tr>
<tr>
<td colspan="2" align="right"><b>总维度：</b></td>
<td align="center"><b>20D</b></td>
<td><b>3+3+3+2+3+2+4 = 20</b></td>
</tr>
</table>

> 💡 **提示**: 观测量总维度为 **20维**，确保你的模型输入与此一致。

---

### 1️⃣ 启动 PX4 SITL 仿真

> 📚 参考文档: [PX4-NeuPilot](https://github.com/WarriorHanamy/PX4-Neupilot)

启动 PX4 仿真和 Micro XRCE-DDS Agent。

---

### 2️⃣ 启动 QGroundControl

```bash
just run-qgc
```

---

### 3️⃣ 启动神经网络控制模式

<table>
<tr>
<th>步骤</th>
<th>终端</th>
<th>命令</th>
<th>说明</th>
</tr>
<tr>
<td align="center">1</td>
<td>终端 1️⃣</td>
<td>

```bash
just run-ros2
```

</td>
<td>进入 ROS2 容器</td>
</tr>
<tr>
<td align="center">2</td>
<td>终端 1️⃣</td>
<td>

```bash
just neural-mode
```

</td>
<td>启动 PX4-ROS2 接口</td>
</tr>
<tr>
<td align="center">3</td>
<td>终端 2️⃣</td>
<td>

```bash
just enter-ros2
```

</td>
<td>另开终端进入容器</td>
</tr>
<tr>
<td align="center">4</td>
<td>终端 2️⃣</td>
<td>

```bash
just neural-inference
```

</td>
<td>启动神经网络推理节点</td>
</tr>
</table>

---

### 4️⃣ 切换到 Demo Start 模式

在 QGroundControl 中选择 **Demo Start** 模式。

---

### 5️⃣ 解锁飞行器

解锁后，飞行器将：
- ✅ 自动起飞
- ✅ 进入 Position 模式

---

### 6️⃣ 激活神经网络控制

通过以下任一方式激活：

<table>
<tr>
<td width="50%">

**🎮 方式 1: 遥控器**
- 触发 `button=1024`

</td>
<td width="50%">

**💻 方式 2: QGroundControl**
- 选择模式: **Neural Control**

</td>
</tr>
</table>

成功后进入 **🧠 神经网络控制模式**！



---

## 📦 包结构

```
📁 ros2_ws/
├── 📂 src/
│   ├── 🧠 neural_manager/             # 神经网络控制核心
│   │   ├── neural_executor/          # 执行器（模式管理与切换）
│   │   ├── neural_pos_ctrl/          # 位置控制（ONNX 推理）
│   │   └── neural_utils/             # 工具包（测试节点）
│   │
│   ├── 🔧 px4-ros2-interface-lib/     # PX4-ROS2 官方接口库
│   │   ├── px4_ros2_cpp/             # 核心 C++ 库
│   │   └── example_mode_*/           # 飞行模式示例
│   │
│   └── 📡 px4_msgs/                   # PX4 消息定义
│
├── 🐳 docker/                         # Docker 配置
├── 🔧 scripts/                        # 实用脚本
└── 📋 justfile                        # 任务运行器
```

### 🎯 核心功能模块

<table>
<tr>
<td align="center" width="33%">

### 🧠
**Neural Executor**
<br>
模式管理与切换

</td>
<td align="center" width="33%">

### 🤖
**Neural Pos Ctrl**
<br>
ONNX 模型推理

</td>
<td align="center" width="33%">

### 🔧
**PX4-ROS2 Lib**
<br>
官方接口库

</td>
</tr>
</table>



---

## 👥 作者信息

**项目维护者**: Arclunar  
**组织**: [Arclunar](https://github.com/Arclunar)  
**仓库**: [px4-ros2-interface](https://github.com/Arclunar/px4-ros2-interface)

**贡献者**:
- WarriorHanamy - 原始仓库贡献者

**联系方式**:
- Issues: [GitHub Issues](https://github.com/Arclunar/px4-ros2-interface/issues)
- Discussions: [GitHub Discussions](https://github.com/Arclunar/px4-ros2-interface/discussions)

---

## 📄 许可证

本项目基于 BSD-3-Clause 许可证开源。详见 [LICENSE](LICENSE) 文件。

---

## 🙏 致谢

- [PX4 Autopilot](https://px4.io/) - 开源飞行控制栈
- [ROS 2](https://docs.ros.org/) - 机器人操作系统
- [px4-ros2-interface-lib](https://github.com/PX4/px4-ros2-interface-lib) - 官方 PX4-ROS2 接口库

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐ Star！**

Made with ❤️ by Arclunar

</div>
