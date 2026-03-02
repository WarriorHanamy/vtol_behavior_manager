# Scripts Directory

## 使用方法

```bash
# 直接执行
./scripts/build.sh
```

## 脚本映射

### ROS2 工作区

| 脚本 | 功能 |
|------|------|
| `build.sh` | 构建 ROS2 工作区（含 px4msgs 配置） |
| `clean.sh` | 清理构建产物 |
| `neural_mode.sh` | 启动 neural executor demo |
| `neural_infer.sh` | 运行 neural inference |

### Docker - ROS2

| 脚本 | 功能 |
|------|------|
| `exec_ros2.sh` | 在 ROS2 容器中执行命令 |

### Docker Compose

| 脚本 | 功能 |
|------|------|
| `docker_up.sh` | 启动 compose 服务 |
| `docker_down.sh` | 停止 compose 服务 |



## 环境变量

## 特点

- ✅ 无硬编码路径，使用 `SCRIPT_DIR` 和 `PROJECT_ROOT` 动态获取
- ✅ 支持环境变量配置
- ✅ 每个脚本独立可执行
- ✅ 遵循 bash 最佳实践（`set -e`）
