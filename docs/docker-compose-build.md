# Docker Compose 构建指南

本文档介绍如何使用 Docker Compose 构建项目的所有 Docker 镜像。

## 前置要求

- Docker Engine 20.10+
- Docker Compose 2.0+
- （可选）代理配置：`~/.docker/config.json`

## 镜像列表

| 服务 | 镜像名 | Dockerfile | 说明 |
|------|--------|------------|------|
| qgc | `qgc5:latest` | `docker/qgc5.dockerfile` | QGroundControl 地面站 |
| ros2 | `ros2-vtol:latest` | `docker/ros2.dockerfile` | ROS2 工作空间 |
| px4 | `px4-gazebo-harmonic:v1` | `docker/px4-gazebo.dockerfile` | PX4 SITL 仿真环境 |

## 构建命令

### 构建所有镜像

```bash
docker compose build
```

### 构建单个镜像

```bash
# QGroundControl
docker compose build qgc

# ROS2 工作空间
docker compose build ros2

# PX4 仿真环境
docker compose build px4
```

### 无缓存构建

```bash
docker compose build --no-cache
```

### 并行构建

```bash
docker compose build --parallel
```

## 网络配置

所有镜像构建时使用 `--network=host` 模式，确保：

1. 可以访问宿主机代理（如果配置了 `~/.docker/config.json`）
2. 可以访问 GitHub 等外部资源
3. 克隆 PX4-Neupilot 子模块

## 代理配置

如果需要使用代理，配置 `~/.docker/config.json`：

```json
{
  "proxies": {
    "default": {
      "httpProxy": "http://127.0.0.1:7890",
      "httpsProxy": "http://127.0.0.1:7890",
      "noProxy": "localhost,127.0.0.1"
    }
  }
}
```

> **⚠️ 重要提示：Dockerfile 中代理变量的正确使用**
>
> 在 Dockerfile 中配置代理时，**务必使用 `ARG` 而非 `ENV`** 来声明 `http_proxy` 相关变量。
>
> **原因说明：**
>
> - `ENV` 定义的变量会成为镜像层的一部分，会被永久 baked 进最终镜像中，这会带来安全风险（代理地址可能包含敏感信息）
> - `ARG` 定义的变量仅在构建时有效，不会出现在最终镜像中，更加安全
> - `ARG` 允许在构建时通过 `--build-arg` 灵活传递不同的代理配置
>
> **正确示例：**
> ```dockerfile
> # 仅在构建时生效
> ARG http_proxy=http://172.17.0.1:7890
> ARG HTTP_PROXY=${http_proxy}
> ARG https_proxy=${http_proxy}
> ARG HTTPS_PROXY=${http_proxy}
> ```
>
> **错误示例：**
> ```dockerfile
> # ❌ 不要这样做！这会将代理地址永久写入镜像
> ENV http_proxy=http://172.17.0.1:7890
> ENV https_proxy=http://172.17.0.1:7890
> ```

## 启动服务

构建完成后，使用 Docker Compose 启动服务：

```bash
# 启动所有服务
docker compose up -d

# 启动单个服务
docker compose up -d qgc
docker compose up -d ros2
docker compose up -d px4

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f
```

## 进入运行中的容器

```bash
# 进入 ROS2 容器
docker compose exec ros2 bash

# 进入 PX4 容器
docker compose exec px4 bash

# 进入 QGC 容器
docker compose exec qgc bash
```

## 停止服务

```bash
# 停止所有服务
docker compose down

# 停止单个服务
docker compose stop qgc
docker compose stop ros2
docker compose stop px4
```

## 与 just 命令对比

| just 命令 | docker compose 等价命令 |
|-----------|------------------------|
| `just build-qgc` | `docker compose build qgc` |
| `just build-ros2` | `docker compose build ros2` |
| `just build-px4` | `docker compose build px4` |
| `just run-qgc` | `docker compose up -d qgc` |
| `just run-ros2` | `docker compose up -d ros2` |
| `just up` | `docker compose up -d` |
| `just down` | `docker compose down` |
| `just dc-restart` | `docker compose restart` |
| `just enter-ros2` | `docker compose exec ros2 bash` |

## 资源限制

默认资源配置：

| 服务 | 内存限制 | 内存预留 |
|------|----------|----------|
| qgc | 2G | 1G |
| ros2 | 8G | 4G |
| px4 | 8G | 4G + GPU |

可在 `docker-compose.yml` 中修改。
