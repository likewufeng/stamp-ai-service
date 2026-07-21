# Stamp AI Service 部署方案

面向 **CPU 服务器 + Docker Compose（仅应用服务，无 Nginx）** 的生产部署说明。

---

## 1. 架构

```
                    Internet
                        │
                        ▼
              ┌──────────────────────────┐
              │ stamp-ai (:18080 宿主机) │  FastAPI + uvicorn
              │  容器内端口 :8000         │
              │  · 印章 / 签名 extract   │
              │  · rembg/u2net           │
              │  · /outputs 静态文件     │
              │  · 定时清理              │
              └────────────┬─────────────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
        data/uploads  data/outputs  data/models/u2net
        data/logs     data/temp
```

| 组件 | 职责 |
| --- | --- |
| **stamp-ai** | 业务服务（印章 / 签名抠图）+ 静态 `/outputs` |
| **数据卷** | 上传、结果、日志、rembg 模型持久化 |

---

## 2. 服务器要求

| 项 | 最低 | 推荐 |
| --- | --- | --- |
| CPU | 2 核 | 4 核+ |
| 内存 | 4 GB | 8 GB+（rembg/onnx 占内存） |
| 磁盘 | 20 GB | 50 GB+（模型 + 历史 outputs） |
| 系统 | Linux x86_64 | Ubuntu 22.04 / Debian 12 |
| 软件 | Docker 24+ / Compose v2 | 同左 |

> **镜像已在构建阶段预下载 `u2net.onnx`（约 176MB）**，无需运行时联网下载，避免 SSL/网络问题。如需离线部署，只需确保构建机器能访问 GitHub/镜像源即可。

---

## 3. 快速部署（推荐）

### 3.1 安装 Docker

```bash
# Ubuntu 示例
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
# 重新登录后生效
docker version
docker compose version
```

### 3.2 获取代码

```bash
git clone <your-repo-url> stamp-ai-service
cd stamp-ai-service
```

### 3.3 一键启动

```bash
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

或手动：

```bash
cp .env.example .env
# 按需编辑 .env

mkdir -p data/{uploads,outputs,logs,temp,models/u2net}

docker compose build
docker compose up -d
docker compose ps
docker compose logs -f stamp-ai
```

### 3.4 验证

```bash
# 经 Nginx
curl -s http://127.0.0.1:18080/api/health

# 或直连应用端口
curl -s http://127.0.0.1:18080/api/health

# 打开文档
# http://<服务器IP>/docs
```

### 3.5 接口冒烟

```bash
# 印章
curl -X POST "http://127.0.0.1:18080/api/stamp/extract" \
  -F "file=@/path/to/stamp.jpg" \
  -F "return_type=base64"

# 签名
curl -X POST "http://127.0.0.1:18080/api/signature/extract" \
  -F "file=@/path/to/sign.jpg" \
  -F "width=800" \
  -F "height=400" \
  -F "return_type=base64"
```

---

## 4. 目录与持久化

部署后本地目录建议：

```text
stamp-ai-service/
├── docker-compose.yml
├── Dockerfile
├── .env                 # 环境变量（勿提交仓库）
├── deploy/
│   ├── deploy.sh
│   ├── nginx/default.conf
│   └── certs/           # HTTPS 证书（可选）
└── data/                # 持久化数据（建议备份）
    ├── uploads/
    ├── outputs/
    ├── logs/
    ├── temp/
    └── models/u2net/    # rembg 模型缓存
```

| 卷 | 容器路径 | 说明 |
| --- | --- | --- |
| `data/uploads` | `/app/data/uploads` | 上传原图 |
| `data/outputs` | `/app/data/outputs` | 结果 PNG / zip |
| `data/logs` | `/app/data/logs` | 应用日志 |
| `data/temp` | `/app/data/temp` | 临时文件 |
| `data/models/u2net` | `/app/data/models/u2net` | 模型，避免重复下载 |

---

## 5. 环境变量（`.env`）

从 `.env.example` 复制：

```bash
cp .env.example .env
```

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `HOST_PORT` | `18080` | 应用端口映射到宿主机 |
| `UVICORN_WORKERS` | `2` | worker 数（CPU 核数相关） |
| `MAX_UPLOAD_BYTES` | `31457280` | 最大上传 30MB |
| `CLEANUP_ENABLED` | `true` | 定时清 uploads/outputs/temp |
| `CLEANUP_MAX_AGE_SECONDS` | `86400` | 文件保留 24h |
| `LOG_RETENTION_DAYS` | `3` | 日志保留天数 |
| `CPU_LIMIT` / `MEM_LIMIT` | `2.0` / `4G` | 容器资源上限 |

---

## 6. 运维命令

```bash
# 查看状态
docker compose ps

# 日志
docker compose logs -f stamp-ai

# 重启
docker compose restart stamp-ai

# 更新发布
git pull
docker compose build stamp-ai
docker compose up -d

# 停止
docker compose down

# 停止并删除数据卷（慎用）
# docker compose down -v
```

---

## 7. HTTPS（可选）

当前 compose **不含 Nginx**。如需 HTTPS，在宿主机或云 SLB 上终结 TLS，反代到：

```text
http://127.0.0.1:18080
```


---

## 8. 生产建议

### 8.1 资源与并发

- rembg / onnxruntime **偏 CPU、内存**；单请求可能数百 MB 峰值。
- `UVICORN_WORKERS=2` 适合 4C8G；机器更小可改为 `1`。
- 不要无脑加 worker，容易 OOM。

### 8.2 磁盘

- 开启清理（默认开）：24h 后清 uploads/outputs/temp。
- 日志默认保留 3 天。
- 定期看 `data/` 占用：`du -sh data/*`。

### 8.3 安全

- 生产环境不要把 `8000` 对公网暴露，按需暴露 `HOST_PORT`（默认 18080）；前面可再挂公司网关/SLB。
  - - 配置防火墙：只放行 80/443/22。
- 如有鉴权需求，在 Nginx 或网关加 API Key / JWT（当前服务默认无鉴权）。

### 8.4 模型管理（重要更新）

**镜像构建时自动下载 `u2net.onnx`**，使用国内镜像源（ghfast.top）加速，失败时回退 GitHub，并校验 MD5。

- **无需手动下载模型**，构建完成即可使用
- **离线部署**：在有网机器执行 `docker compose build` 生成镜像，再 `docker save` 导出，拷贝到离线机器 `docker load`
- **模型路径**：容器内 `/app/data/models/u2net/u2net.onnx`，对应宿主机 `data/models/u2net/u2net.onnx`
- **环境变量**：`U2NET_HOME=/app/data/models/u2net` 已在 Dockerfile 和 compose 中配置

### 8.5 健康检查与监控

- 存活探针：`GET /api/health`
- 容器自带 Docker healthcheck
- 可把 Nginx / 应用日志接入 Loki、ELK 或云监控

---

## 9. 不使用 Docker（裸机 systemd）

适合已有 Python 环境的内网机。

```bash
# 1) Python 3.10–3.12
sudo apt update
sudo apt install -y python3-venv python3-pip libgl1 libglib2.0-0

# 2) 项目
cd /opt/stamp-ai-service
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

# 3) 目录
mkdir -p uploads outputs logs temp models/u2net
export U2NET_HOME=/opt/stamp-ai-service/models/u2net

# 4) 启动
uvicorn app:app --host 0.0.0.0 --port 18080 --workers 2
```

systemd 单元示例 `/etc/systemd/system/stamp-ai.service`：

```ini
[Unit]
Description=Stamp AI Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/stamp-ai-service
Environment=U2NET_HOME=/opt/stamp-ai-service/models/u2net
Environment=UVICORN_WORKERS=2
Environment=CLEANUP_ENABLED=true
Environment=LOG_RETENTION_DAYS=3
ExecStart=/opt/stamp-ai-service/.venv/bin/uvicorn app:app --host 127.0.0.1 --port 18080 --workers 2 --proxy-headers
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now stamp-ai
sudo systemctl status stamp-ai
```

前面再挂一层 Nginx 反代到 `127.0.0.1:18080` 即可。

---

## 10. 常见问题

### 构建慢 / 拉包失败

使用国内镜像：

```bash
# 构建时
docker compose build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

或在 Dockerfile 的 `pip install` 增加 `-i`。

### 模型下载失败（构建阶段）

Dockerfile 已配置双镜像源（ghfast.top 优先，GitHub 回退）并校验 MD5。若仍失败：

1. 检查构建机器网络：`curl -I https://ghfast.top/https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx`
2. 手动下载模型放入构建上下文，修改 Dockerfile 使用 `COPY` 而非 `curl`

```bash
# 手动下载（有网机器）
mkdir -p data/models/u2net
curl -fL -o data/models/u2net/u2net.onnx "https://ghfast.top/https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx"
# 然后在 Dockerfile 中将下载步骤改为：
# COPY data/models/u2net/u2net.onnx /app/data/models/u2net/u2net.onnx
```

### 首次请求很慢

模型已在构建阶段下载，容器启动后首次请求仅加载 ONNX 模型到内存（约 1-2 秒），属正常。

### 内存不足 OOM

- `UVICORN_WORKERS=1`
- 降低 `MEM_LIMIT` 仅作限制，真正要加机器内存
- 控制上传图分辨率 / `MAX_IMAGE_PIXELS`

### OpenCV / libGL 报错

镜像已装 `libgl1` 并用 `opencv-python-headless`。裸机请安装：

```bash
sudo apt install -y libgl1 libglib2.0-0
```

### 权限问题（volume 无法写）

```bash
sudo chown -R 1000:1000 data
# 或与容器 appuser uid 对齐
```

---

## 11. 发布检查清单

- [ ] `.env` 已按环境修改
- [ ] `data/` 目录已创建且可写
- [ ] `docker compose ps` 全部 healthy
- [ ] `/api/health` 返回正常
- [ ] `/docs` 可打开
- [ ] 印章、签名各测 1 张真实图
- [ ] 防火墙 / 安全组只开放必要端口
- [ ] 备份策略：是否需要备份 `data/outputs`（一般可只保留短期）
- [ ] 日志与磁盘巡检（`df -h`、`du -sh data/*`）

---

## 12. 相关文件

| 路径 | 说明 |
| --- | --- |
| `Dockerfile` | 生产镜像（含构建期模型下载） |
| `docker-compose.yml` | 仅应用服务 |
| `.env.example` | 环境变量模板 |
| `deploy/deploy.sh` | 一键部署脚本 |
| `utils/cleanup.py` | 上传/输出定时清理 |
| `config.py` | 运行时配置 |

按本方案，标准路径是：

```bash
./deploy/deploy.sh
# 浏览器打开 http://服务器IP:18080/docs
```
