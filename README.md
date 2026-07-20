### 为了提高生产环境的稳定性，我还建议加入以下优化：

```
自动识别多个印章。
自动旋转和透视校正（适应拍照件）。
自动去除表格线。
自动去除文字干扰。
自动判断印章颜色（红、蓝、黑）。
自动补全断裂笔画。
边缘羽化（减少锯齿）。
导出真正的透明 PNG（Alpha 通道）。
输出印章中心点、外接矩形、面积等信息。
支持 GPU 和 CPU 自动切换。
模型单例加载，避免每次请求重复加载模型。
异步接口处理。
请求日志与异常日志记录。
文件大小、图片尺寸等参数校验。
Docker 与 Docker Compose 部署支持。
Nginx 反向代理配置。
```

### 如果目标是企业级、长期维护的项目，我建议采用以下架构：

```
FastAPI 提供 REST API。
YOLO11 负责印章目标检测。
SAM2 负责高精度分割。
OpenCV 负责后处理（去噪、平滑、透明化）。
Redis（可选）用于缓存与任务状态。
Celery（可选）处理耗时任务。
Docker 部署，Nginx 提供反向代理。
Swagger 自动生成接口文档。
这套架构能够较好地应对复杂的印章采集表、扫描件和拍照件，并具备较好的扩展性和部署便利性
```

### 我建议按照以下开发顺序推进，每一步我都会给出完整可运行代码：
```
第一步：项目骨架、FastAPI、配置、日志、Docker、基础接口。
第二步：YOLO11 检测模块与模型管理。
第三步：BiRefNet/U²-Net 分割模块与透明 PNG 导出。
第四步：OpenCV 后处理（去表格线、去文字干扰、羽化等）。
第五步：批量处理、ZIP 输出、性能优化、测试与部署文档。
```

真正的生产方案（我推荐）
自己训练 YOLO11 印章检测模型。
我帮你提供数据集格式、训练脚本和推理代码。
精度最高。
无需训练的方案（推荐作为 V1）
利用传统视觉算法自动定位印章，再用 AI 做精细分割。


```
                    FastAPI
                        │
                        ▼
                DocumentService
                        │
        ┌───────────────┼────────────────┐
        │               │                │
        ▼               ▼                ▼
 DocumentDetector   Perspective     Orientation
   (文档检测)         (透视)          (方向校正)
        │
        ▼
     Paper Image
        │
        ▼
 Layout Analyzer（版面分析）
        │
 ┌──────┴──────────┐
 │                 │
 ▼                 ▼
TableDetector   StampDetector
 │                 │
 ▼                 ▼
表格区域        所有印章区域
        │
        └──────┬──────────────┐
               ▼              ▼
        StampSegmentor   OCR(可选)
               │
               ▼
        Alpha Composer
               │
               ▼
          Transparent PNG
```

---

## 印章抠图接口

### `POST /api/stamp/extract`

从扫描件 / 拍照件中检测印章，抠出透明 PNG。

#### 请求（multipart/form-data）

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | file | 是 | - | 图片文件（jpg/jpeg/png/bmp/webp/tif/tiff） |
| `debug` | bool | 否 | `false` | 是否输出调试文件（检测框、mask 等） |
| `correct_perspective` | bool | 否 | `true` | 是否尝试文档透视校正 |
| `return_type` | string | 否 | `base64` | 返回方式：`url` / `base64` / `both` |

#### `return_type` 说明

| 取值 | 行为 |
| --- | --- |
| `base64`（默认） | 每个印章返回 `base64`，`url` / `zip_url` 为 `null` |
| `url` | 每个印章返回 `url`，并生成 `zip_url`，`base64` 为 `null` |
| `both` | 同时返回 `url`、`base64`，并生成 `zip_url` |

#### 返回示例

```json
{
  "request_id": "a1b2c3d4e5f6",
  "filename": "stamp_scan.jpg",
  "original_width": 1600,
  "original_height": 2400,
  "processed_width": 1600,
  "processed_height": 2400,
  "perspective_applied": false,
  "return_type": "base64",
  "count": 2,
  "stamps": [
    {
      "index": 1,
      "box": {
        "x": 120,
        "y": 340,
        "w": 180,
        "h": 180,
        "confidence": 1.0,
        "label": "stamp",
        "color": "red"
      },
      "width": 200,
      "height": 200,
      "file_name": "stamp_001.png",
      "url": null,
      "base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
    },
    {
      "index": 2,
      "box": {
        "x": 520,
        "y": 360,
        "w": 160,
        "h": 160,
        "confidence": 1.0,
        "label": "stamp",
        "color": "red"
      },
      "width": 180,
      "height": 180,
      "file_name": "stamp_002.png",
      "url": null,
      "base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
    }
  ],
  "zip_url": null,
  "debug_files": []
}
```

#### 返回字段说明

| 字段 | 说明 |
| --- | --- |
| `request_id` | 本次请求 ID，也是输出目录名 |
| `filename` | 原始上传文件名 |
| `original_width` / `original_height` | 原图尺寸 |
| `processed_width` / `processed_height` | 预处理后尺寸 |
| `perspective_applied` | 是否实际做了透视校正 |
| `return_type` | 本次实际使用的返回方式 |
| `count` | 检出印章数量 |
| `stamps` | 印章列表 |
| `stamps[].box` | 印章外接矩形（x/y/w/h）及颜色、置信度 |
| `stamps[].width` / `height` | 输出透明 PNG 尺寸 |
| `stamps[].file_name` | 输出文件名，如 `stamp_001.png` |
| `stamps[].url` | 静态访问路径：`/outputs/{request_id}/stamp_001.png` |
| `stamps[].base64` | `data:image/png;base64,...`，可直接用于前端 `<img src>` |
| `zip_url` | 全部印章打包下载路径：`/outputs/{request_id}/stamps.zip` |
| `debug_files` | `debug=true` 时的调试文件 URL 列表 |

#### 调用示例

```bash
# 默认：只返回 base64
curl -X POST "http://127.0.0.1:8000/api/stamp/extract" \
  -F "file=@stamp_scan.jpg"

# 只返回 URL + ZIP
curl -X POST "http://127.0.0.1:8000/api/stamp/extract" \
  -F "file=@stamp_scan.jpg" \
  -F "return_type=url"

# 同时返回 URL 和 base64
curl -X POST "http://127.0.0.1:8000/api/stamp/extract" \
  -F "file=@stamp_scan.jpg" \
  -F "return_type=both"

# 开启调试 + 关闭透视校正
curl -X POST "http://127.0.0.1:8000/api/stamp/extract" \
  -F "file=@stamp_scan.jpg" \
  -F "return_type=both" \
  -F "debug=true" \
  -F "correct_perspective=false"
```

#### 错误码

| HTTP 状态码 | 说明 |
| --- | --- |
| `400` | 文件为空、格式不支持、参数非法、图片处理失败 |
| `413` | 上传文件过大 |
| `500` | 服务器内部处理异常 |

#### 说明

- 支持一次检出多个印章
- 输出为透明 PNG（Alpha 通道）
- 访问 `url` / `zip_url` 时，服务需已挂载静态目录 `/outputs`
- 在线调试文档：`http://127.0.0.1:8000/docs`

---

## 手写签名抠图接口（v0.6.0 · rembg）

### 方案说明

采用 rembg 去背景方案，核心流程：

1. **rembg** AI 去背景（主路径）
2. 对比度增强，提升淡铅笔可见度
3. 传统暗度阈值作为 **fallback**（rembg 对极淡笔迹失效时启用）
4. 笔画转 **纯黑**，背景透明
5. 自动裁空白 + padding
6. **等比缩放居中**到自定义宽高画布（不变形）
7. 支持返回 **url / base64 / both**

### `POST /api/signature/extract`

#### 请求（multipart/form-data）

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `file` | file | 是 | - | 签名图片（白纸手写 / 扫描 / 拍照） |
| `width` | int | 否 | - | 输出宽度（1~4096）。可只传一边 |
| `height` | int | 否 | - | 输出高度（1~4096）。可只传一边 |
| `resize_mode` | string | 否 | `fit` | `fit`（等比居中不变形）/ `fill` / `stretch` |
| `return_type` | string | 否 | `base64` | `url` / `base64` / `both` |
| `padding` | int | 否 | `30` | 裁切后四周留白 |
| `debug` | bool | 否 | `false` | 输出调试文件 |

#### 尺寸适配（防变形）

- `fit`：等比缩放后居中放入画布，空白透明（推荐）
- 只传 `width` 或 `height`：另一边自动按比例计算
- `fill`：等比铺满后裁剪
- `stretch`：强制拉伸（会变形，不推荐）

#### 调用示例

```bash
# 默认返回 base64
curl -X POST "http://127.0.0.1:8000/api/signature/extract" \
  -F "file=@signature.jpg" \
  -F "width=800" \
  -F "height=400"

# 返回 URL
curl -X POST "http://127.0.0.1:8000/api/signature/extract" \
  -F "file=@signature.jpg" \
  -F "width=400" \
  -F "height=200" \
  -F "return_type=url"

# 同时返回 url + base64
curl -X POST "http://127.0.0.1:8000/api/signature/extract" \
  -F "file=@signature.jpg" \
  -F "width=512" \
  -F "height=256" \
  -F "return_type=both"
```

#### 返回字段要点

- `signatures[0].url`：`/outputs/{request_id}/signature_001.png`
- `signatures[0].base64`：`data:image/png;base64,...`
- `content_width / content_height`：签名在画布中的实际占用尺寸

#### 依赖说明

```bash
pip install -r requirements.txt
# 首次运行会自动下载 u2net.onnx（约 176MB）到 ~/.u2net/
```

---

## 定时清理 uploads / outputs

服务启动后会自动开启后台清理任务，定期删除 `uploads/`、`outputs/`、`temp/` 中的过期文件，避免磁盘被历史请求占满。

### 默认策略

| 项 | 默认值 | 说明 |
| --- | --- | --- |
| 是否启用 | `true` | `CLEANUP_ENABLED` |
| 扫描间隔 | `3600` 秒（1 小时） | `CLEANUP_INTERVAL_SECONDS` |
| 保留时长 | `86400` 秒（24 小时） | `CLEANUP_MAX_AGE_SECONDS` |
| 清理目录 | `uploads` / `outputs` / `temp` | 见 `config.CLEANUP_DIRS` |

### 删除规则

- `uploads/` 下单文件：按文件 `mtime` 超期删除
- `outputs/{request_id}/`：按目录内**最新内容**的 `mtime` 判断，整个请求目录一次性删除
- `temp/`：同上
- **不会**删除 `uploads` / `outputs` / `temp` 根目录本身
- 启动时会先执行一轮清理，之后按间隔循环

### 环境变量示例

```bash
# 关闭清理
export CLEANUP_ENABLED=false

# 每 30 分钟扫一次，只保留 12 小时
export CLEANUP_INTERVAL_SECONDS=1800
export CLEANUP_MAX_AGE_SECONDS=43200

python app.py
```

### 相关代码

- `config.py`：清理配置
- `utils/cleanup.py`：清理实现（后台线程）
- `app.py`：`lifespan` 中启动/停止清理任务

### 日志自动清理

应用日志由 loguru 管理，默认只保留最近 **3 天**：

| 项 | 默认值 | 环境变量 |
| --- | --- | --- |
| 日志文件 | `logs/service.log` | - |
| 单文件滚动 | `50 MB` | - |
| 保留天数 | `3` 天 | `LOG_RETENTION_DAYS` |

```bash
# 例如改为保留 7 天
export LOG_RETENTION_DAYS=7
python app.py
```
