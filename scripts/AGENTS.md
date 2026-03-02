# Scripts Directory

此目录包含从 `justfile` 迁移过来的 bash 脚本。所有脚本都是可配置的，不支持硬编码路径。

## 使用方法

```bash
# 直接执行
./scripts/build.sh

# 或者使用绝对路径
/home/rec/server/vtol-interface/scripts/build.sh
```

## 脚本映射

### ROS2 工作区

| 脚本 | 功能 |
|------|------|
| `build.sh` | 构建 ROS2 工作区 |
| `full_build.sh` | 完整构建（config_px4msgs + build） |
| `clean.sh` | 清理构建产物 |
| `example.sh` | 运行 ROS2 example 节点 |
| `neural_mode.sh` | 启动 neural executor demo |
| `neural_infer.sh` | 运行 neural inference |

### Docker - ROS2

| 脚本 | 功能 |
|------|------|
| `build_ros2.sh` | 构建 ROS2 Docker 镜像 |
| `build_ros2_podman.sh` | 使用 Podman 构建 ROS2 镜像 |
| `run_ros2.sh` | 运行 ROS2 容器 |
| `run_ros2_podman.sh` | 使用 Podman 运行 ROS2 容器 |
| `enter_ros2.sh` | 进入运行中的 ROS2 容器 |
| `develop_ros2.sh` | 后台运行 ROS2 开发容器 |

### Docker - QGroundControl

| 脚本 | 功能 |
|------|------|
| `build_qgc.sh` | 构建 QGC5 Docker 镜像 |
| `run_qgc.sh` | 运行 QGC 容器 |

### Docker - PX4 Gazebo

| 脚本 | 功能 |
|------|------|
| `build_px4.sh` | 构建 PX4 Gazebo Docker 镜像 |
| `run_px4.sh [model]` | 运行 PX4 仿真（可指定模型，默认 2） |
| `enter_px4.sh` | 进入运行中的 PX4 容器 |
| `clean_px4.sh` | 删除 PX4 容器 |

### Docker Compose

| 脚本 | 功能 |
|------|------|
| `docker_up.sh` | 启动 compose 服务 |
| `docker_down.sh` | 停止 compose 服务 |
| `docker_restart.sh` | 重启 compose 服务 |
| `df_docker.sh` | 查看 Docker 磁盘使用 |

### 其他

| 脚本 | 功能 |
|------|------|
| `config_px4msgs.sh` | 配置 PX4 消息（已存在） |
| `killall.sh` | 杀死所有相关进程（已存在） |
| `build_px4_gazebo.sh` | 构建 PX4 Gazebo（已存在） |

## 环境变量

部分脚本支持以下环境变量：

- `PROXY_HOST`: 代理主机（默认：`internal_proxy`）
- `PROXY_PORT`: 代理端口（默认：`7890`）
- `ROS_DISTRO`: ROS2 发行版（如 `humble`, `foxy`）

## 特点

- ✅ 无硬编码路径，使用 `SCRIPT_DIR` 和 `PROJECT_ROOT` 动态获取
- ✅ 支持环境变量配置
- ✅ 每个脚本独立可执行
- ✅ 遵循 bash 最佳实践（`set -e`）
