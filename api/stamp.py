# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 09:42:45
#LastEditTime: 2026-07-20 09:46:23
#LastEditors: WuFeng <763467339@qq.com>
#Description: 印章识别接口
#FilePath: /stamp-ai-service/api/stamp.py
#Copyright 版权声明
#
import functools
import uuid
from pathlib import Path

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
from core.services.service import stamp_service
from schemas.stamp import StampExtractionResponse


router = APIRouter(
    prefix="/api/stamp",
    tags=["Stamp"],
)


@router.post(
    "/extract",
    response_model=StampExtractionResponse,
    summary="提取图片中的所有印章",
)
async def extract(
    file: UploadFile = File(...),
    # 是否开启调试模式
    debug: bool = Form(default=False),
    # 是否纠正透视
    correct_perspective: bool = Form(default=True),
    # 返回方式：url / base64 / both
    return_type: str = Form(
        default="base64",
        description="返回方式：url / base64 / both（默认 base64）",
    ),
):
    source_filename = (
        file.filename or "unknown"
    )

    extension = Path(
        source_filename
    ).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "不支持的图片格式，允许格式："
                + ", ".join(
                    sorted(ALLOWED_EXTENSIONS)
                )
            ),
        )

    normalized_return_type = (
        return_type or "base64"
    ).strip().lower()

    if normalized_return_type not in {
        "url",
        "base64",
        "both",
    }:
        raise HTTPException(
            status_code=400,
            detail="return_type 仅支持 url / base64 / both",
        )

    file_data = await file.read(
        MAX_UPLOAD_BYTES + 1
    )

    await file.close()

    if not file_data:
        raise HTTPException(
            status_code=400,
            detail="上传文件为空",
        )

    if len(file_data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                "上传文件过大，最大允许 "
                f"{MAX_UPLOAD_BYTES // 1024 // 1024}MB"
            ),
        )

    stored_filename = (
        f"{uuid.uuid4().hex}{extension}"
    )

    save_path = UPLOAD_DIR / stored_filename

    try:
        async with aiofiles.open(
            save_path,
            "wb",
        ) as output_file:
            await output_file.write(file_data)

        process_function = functools.partial(
            stamp_service.process_image,
            file_path=str(save_path),
            source_filename=source_filename,
            debug=debug,
            correct_perspective=(
                correct_perspective
            ),
            return_type=normalized_return_type,
        )

        result = await run_in_threadpool(
            process_function
        )

        logger.info(
            "印章提取完成 filename={} count={} return_type={}",
            source_filename,
            result.count,
            normalized_return_type,
        )

        return result

    except ValueError as exc:
        logger.warning(
            "图片处理失败 filename={} error={}",
            source_filename,
            str(exc),
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "印章提取异常 filename={}",
            source_filename,
        )

        raise HTTPException(
            status_code=500,
            detail="服务器处理图片失败",
        ) from exc
