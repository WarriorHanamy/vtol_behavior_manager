#!/bin/bash
set -e  # 遇到错误立即退出

echo "🚀 开始构建 PX4 Simulator 容器..."

# 定义临时目录
TEMP_DIR=$(mktemp -d)
REPO_URL="https://github.com/WarriorHanamy/PX4-Neupilot.git"

# 清理函数
cleanup() {
    echo "🧹 清理临时目录: $TEMP_DIR"
    rm -rf "$TEMP_DIR"
}

# 设置退出时自动清理
trap cleanup EXIT

echo "📥 克隆仓库到临时目录: $TEMP_DIR"
git clone "$REPO_URL" --recursive --depth 1 "$TEMP_DIR/PX4-Neupilot"

echo "📂 进入仓库目录"
cd "$TEMP_DIR/PX4-Neupilot"

echo "🏗️  开始构建 PX4 容器镜像..."
just build-px4

echo "✅ PX4 Simulator 容器构建完成！"
echo "🎉 临时文件将自动清理"
