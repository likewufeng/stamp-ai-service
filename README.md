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

## 手写签名抠图接口（v0.6.0 · rembg）

### 方案说明

采用你提供的思路，核心流程：

1. **rembg** AI 去背景（主路径）
2. 对比度增强，提升淡铅笔可见度
3. 传统暗度阈值作为 **fallback**（rembg 对极淡笔迹失效时启用）
4. 笔画转 **纯黑**，背景透明
5. 自动裁空白 + padding
6. **等比缩放居中**到自定义宽高画布（不变形）
7. 支持返回 **url / base64 / both**

### `POST /api/signature/extract`

#### 请求（multipart/form-data）

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `file` | file | 是 | 签名图片（白纸手写 / 扫描 / 拍照） |
| `width` | int | 否 | 输出宽度（1~4096）。可只传一边 |
| `height` | int | 否 | 输出高度（1~4096）。可只传一边 |
| `resize_mode` | string | 否 | `fit`（默认，等比居中不变形）/ `fill` / `stretch` |
| `return_type` | string | 否 | `url`（默认）/ `base64` / `both` |
| `padding` | int | 否 | 裁切后四周留白，默认 `30` |
| `debug` | bool | 否 | 输出调试文件，默认 `false` |

#### 尺寸适配（防变形）

- `fit`：等比缩放后居中放入画布，空白透明（推荐）
- 只传 `width` 或 `height`：另一边自动按比例计算
- `fill`：等比铺满后裁剪
- `stretch`：强制拉伸（会变形，不推荐）

#### 调用示例

```bash
# 输出 800x400 透明签名 PNG，返回 URL
curl -X POST "http://127.0.0.1:8000/api/signature/extract" \
  -F "file=@signature.jpg" \
  -F "width=800" \
  -F "height=400" \
  -F "resize_mode=fit" \
  -F "return_type=url" \
  -F "padding=30"

# 返回 base64（可直接给前端 img src）
curl -X POST "http://127.0.0.1:8000/api/signature/extract" \
  -F "file=@signature.jpg" \
  -F "width=400" \
  -F "height=200" \
  -F "return_type=base64"

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