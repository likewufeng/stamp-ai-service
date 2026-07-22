#!/usr/bin/env bash
###
 # @Author: WuFeng <763467339@qq.com>
 # @Date: 2026-07-22 10:09:14
 # @LastEditTime: 2026-07-22 11:22:37
 # @LastEditors: WuFeng <763467339@qq.com>
 # @Description: 本地开发启动脚本（无需 Docker，跨平台：Linux/macOS/Windows Git Bash）
  # 用法: ./dev.sh [端口号]
  #   端口号可选，默认读取 .env 中的 HOST_PORT 或 18080
  #   例: ./dev.sh 18081
  # 用法: ./dev.sh
  # ✅ 检测平台 → 用正确路径激活虚拟环境
  # ✅ 创建/复用 .venv
  # ✅ 安装依赖（requirements.txt）
  # ✅ 创建 data/ 目录
  # ✅ 预下载 u2net.onnx 模型
  # ✅ 启动 uvicorn --reload 热重载
 # @FilePath: /stamp-ai-service/dev.sh
 # Copyright 版权声明
### 

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "=== Stamp AI Service - 本地开发模式 ==="
echo "工作目录: $ROOT_DIR"

# ──────────────────────────────────────────────
# 跨平台路径检测
# ──────────────────────────────────────────────
if [[ -f ".venv/Scripts/activate" ]]; then
    # Windows (Git Bash / MSYS / Cygwin)
    VENV_ACTIVATE=".venv/Scripts/activate"
    PYTHON_CMD="python"
    IS_WINDOWS=1
elif [[ -f ".venv/bin/activate" ]]; then
    # Linux / macOS
    VENV_ACTIVATE=".venv/bin/activate"
    PYTHON_CMD="python3"
    IS_WINDOWS=0
else
    # 未创建虚拟环境，按当前平台推断
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || -n "${WINDIR:-}" ]]; then
        VENV_ACTIVATE=".venv/Scripts/activate"
        PYTHON_CMD="python"
        IS_WINDOWS=1
    else
        VENV_ACTIVATE=".venv/bin/activate"
        PYTHON_CMD="python3"
        IS_WINDOWS=0
    fi
fi

# ──────────────────────────────────────────────
# 端口处理：优先级 CLI参数 > .env(HOST_PORT) > .env(APP_PORT) > 默认18080
# ──────────────────────────────────────────────
PORT="${1:-}"
if [[ -z "$PORT" && -f .env ]]; then
    # 本地开发优先用 HOST_PORT（宿主机端口），其次 APP_PORT（容器端口）
    PORT=$(grep -E '^HOST_PORT=' .env 2>/dev/null | cut -d'=' -f2 | tr -d ' "') || true
    if [[ -z "$PORT" ]]; then
        PORT=$(grep -E '^APP_PORT=' .env 2>/dev/null | cut -d'=' -f2 | tr -d ' "') || true
    fi
fi
PORT="${PORT:-18080}"

# ──────────────────────────────────────────────
# 信号处理：优雅关闭
# ──────────────────────────────────────────────
UVICORN_PID=""

cleanup() {
    echo ""
    echo "=== 收到停止信号，正在关闭服务 ==="
    if [[ -n "$UVICORN_PID" ]]; then
        if [[ $IS_WINDOWS -eq 1 ]]; then
            # Windows: taskkill 进程树
            taskkill //PID "$UVICORN_PID" //T //F >/dev/null 2>&1 || true
        else
            # Unix: 发送 SIGTERM 到进程组
            kill -TERM -"$UVICORN_PID" 2>/dev/null || kill -TERM "$UVICORN_PID" 2>/dev/null || true
        fi
        # 等待进程退出（最多 5 秒）
        for i in {1..10}; do
            if ! kill -0 "$UVICORN_PID" 2>/dev/null; then
                break
            fi
            sleep 0.5
        done
        echo "服务已停止"
    fi
    exit 0
}

# 捕获常见信号
trap cleanup INT TERM EXIT

# Windows Git Bash 额外捕获 SIGBREAK (Ctrl+Break)
# 注意：Git Bash 中信号名不识别 SIGBREAK，使用数值 21
if [[ $IS_WINDOWS -eq 1 ]]; then
    trap cleanup 21 2>/dev/null || true
fi

# ──────────────────────────────────────────────
# 端口冲突检测与自动重试
# ──────────────────────────────────────────────
check_port() {
    local port=$1
    if [[ $IS_WINDOWS -eq 1 ]]; then
        # Windows: netstat
        netstat -ano | grep -q ":$port " && return 1 || return 0
    else
        # Unix: lsof 或 ss
        (lsof -i ":$port" >/dev/null 2>&1) || (ss -ltn | grep -q ":$port ") && return 1 || return 0
    fi
}

find_free_port() {
    local port=$1
    local max_try=10
    for ((i=0; i<max_try; i++)); do
        if check_port "$port"; then
            echo "$port"
            return 0
        fi
        echo "⚠️  端口 $port 被占用，尝试 $((port+1))..."
        port=$((port+1))
    done
    echo "❌ 连续 $max_try 个端口均被占用，请手动指定端口: ./dev.sh <port>"
    exit 1
}

PORT=$(find_free_port "$PORT")

# ──────────────────────────────────────────────
# 1. 检查 .env
# ──────────────────────────────────────────────
if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    echo "未发现 .env，从 .env.example 复制..."
    cp .env.example .env
  else
    echo "⚠️  无 .env.example，将使用默认配置"
  fi
fi

# ──────────────────────────────────────────────
# 2. 检查/创建虚拟环境
# ──────────────────────────────────────────────
if [[ ! -d .venv ]]; then
  echo "创建虚拟环境 .venv ..."
  $PYTHON_CMD -m venv .venv
fi

# ──────────────────────────────────────────────
# 3. 激活虚拟环境并安装依赖
# ──────────────────────────────────────────────
echo "激活虚拟环境并安装依赖..."
# shellcheck disable=SC1090
source "$VENV_ACTIVATE"
# Windows 下用 python -m pip 避免 pip.exe 被锁定/拒绝访问
$PYTHON_CMD -m pip install -q --upgrade pip
$PYTHON_CMD -m pip install -q -r requirements.txt

# ──────────────────────────────────────────────
# 4. 创建数据目录
# ──────────────────────────────────────────────
mkdir -p data/uploads data/outputs data/logs data/temp data/models/u2net

# ──────────────────────────────────────────────
# 5. 预下载模型（可选，避免首次请求等待）
# ──────────────────────────────────────────────
if [[ ! -f data/models/u2net/u2net.onnx ]]; then
  echo "预下载 u2net.onnx 模型..."
  $PYTHON_CMD -c "
import os, hashlib, requests, sys
url = 'https://ghfast.top/https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx'
path = 'data/models/u2net/u2net.onnx'
os.makedirs(os.path.dirname(path), exist_ok=True)
try:
    r = requests.get(url, stream=True, timeout=300)
    r.raise_for_status()
    with open(path, 'wb') as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    md5 = hashlib.md5(open(path, 'rb').read()).hexdigest()
    expected = '60024c5c889badc19c04ad937298a77b'
    if md5 != expected:
        print(f'MD5 校验失败: {md5} != {expected}', file=sys.stderr)
        sys.exit(1)
    print(f'模型下载完成，MD5: {md5}')
except Exception as e:
    print(f'下载失败: {e}', file=sys.stderr)
    sys.exit(1)
  " || echo "⚠️  模型下载失败，首次请求时会自动下载"
fi

# ──────────────────────────────────────────────
# 6. 启动服务（开启 reload 热重载）
# ──────────────────────────────────────────────
echo ""
echo "=== 启动服务 (热重载开启) ==="
echo "API 文档: http://127.0.0.1:$PORT/docs"
echo "健康检查: http://127.0.0.1:$PORT/api/health"
echo ""
echo "────────────────────────────────────────"
echo "停止方式："
echo "  - Ctrl+C          (标准终止)"
if [[ $IS_WINDOWS -eq 1 ]]; then
echo "  - Ctrl+Break      (Windows 强制终止，更可靠)"
fi
echo "  - 关闭终端窗口     (脚本会自动清理进程)"
echo "────────────────────────────────────────"
echo ""

# 后台启动 uvicorn，捕获 PID
uvicorn app:app --host 0.0.0.0 --port "$PORT" --reload &
UVICORN_PID=$!

# 等待子进程（trap 会在退出时清理）
wait $UVICORN_PID