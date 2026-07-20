# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-19
#Description: 手写签名抠图接口（rembg）
#FilePath: /stamp-ai-service/api/signature.py
#
import functools
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from loguru import logger
from starlette.concurrency import run_in_threadpool

from config import (
    ALLOWED_EXTENSIONS,
    MAX_UPLOAD_BYTES,
    UPLOAD_DIR,
)
from core.services.signature_service import signature_service
from schemas.signature import SignatureExtractionResponse


router = APIRouter(
    prefix="/api/signature",
    tags=["Signature"],
)


@router.post(
    "/extract",
    response_model=SignatureExtractionResponse,
    summary="提取手写签名（rembg 去背景 + 透明 PNG）",
)
async def extract(
    file: UploadFile = File(
        ...,
        description="签名图片（白纸手写 / 扫描 / 拍照）",
    ),
    width: Optional[int] = Form(
        default=None,
        description="输出宽度（像素）。可只传一边，另一边自动等比",
        ge=1,
        le=4096,
    ),
    height: Optional[int] = Form(
        default=None,
        description="输出高度（像素）。可只传一边，另一边自动等比",
        ge=1,
        le=4096,
    ),
    resize_mode: str = Form(
        default="fit",
        description="fit(等比居中不变形，推荐) / fill(等比铺满裁剪) / stretch(强制拉伸)",
    ),
    return_type: str = Form(
        default="base64",
        description="返回方式：url / base64 / both（默认 base64）",
    ),
    padding: int = Form(
        default=30,
        description="签名裁切后四周留白像素",
        ge=0,
        le=200,
    ),
    debug: bool = Form(
        default=False,
        description="是否输出调试文件",
    ),
):
    source_filename = file.filename or "unknown"
    extension = Path(source_filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "不支持的图片格式，允许格式："
                + ", ".join(sorted(ALLOWED_EXTENSIONS))
            ),
        )

    normalized_return_type = (return_type or "base64").strip().lower()
    if normalized_return_type not in {"url", "base64", "both"}:
        raise HTTPException(
            status_code=400,
            detail="return_type 仅支持 url / base64 / both",
        )

    normalized_resize_mode = (resize_mode or "fit").strip().lower()
    if normalized_resize_mode not in {"fit", "fill", "stretch"}:
        raise HTTPException(
            status_code=400,
            detail="resize_mode 仅支持 fit / fill / stretch",
        )

    file_data = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()

    if not file_data:
        raise HTTPException(status_code=400, detail="上传文件为空")

    if len(file_data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                "上传文件过大，最大允许 "
                f"{MAX_UPLOAD_BYTES // 1024 // 1024}MB"
            ),
        )

    stored_filename = f"{uuid.uuid4().hex}{extension}"
    save_path = UPLOAD_DIR / stored_filename

    try:
        async with aiofiles.open(save_path, "wb") as output_file:
            await output_file.write(file_data)

        process_function = functools.partial(
            signature_service.process_image,
            file_path=str(save_path),
            source_filename=source_filename,
            debug=debug,
            target_width=width,
            target_height=height,
            resize_mode=normalized_resize_mode,
            return_type=normalized_return_type,
            padding=padding,
        )

        result = await run_in_threadpool(process_function)

        logger.info(
            "签名提取完成 filename={} count={} return_type={} size={}x{}",
            source_filename,
            result.count,
            normalized_return_type,
            width,
            height,
        )
        return result

    except ValueError as exc:
        logger.warning(
            "签名处理失败 filename={} error={}",
            source_filename,
            str(exc),
        )
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "签名提取异常 filename={}",
            source_filename,
        )
        raise HTTPException(
            status_code=500,
            detail="服务器处理图片失败",
        ) from exc
