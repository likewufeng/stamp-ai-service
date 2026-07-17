# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 09:42:45
#LastEditTime: 2026-07-17 10:49:11
#LastEditors: WuFeng <763467339@qq.com>
#Description: 印章识别接口
#FilePath: /stamp-ai-service/api/stamp.py
#Copyright 版权声明
#
import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File
from config import UPLOAD_DIR
from core.service import StampService

router = APIRouter(prefix="/api/stamp", tags=["Stamp"])

@router.post("/extract")
async def extract(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix
    filename = f"{uuid.uuid4()}{ext}"
    save_path = UPLOAD_DIR / filename

    # 1. 保存文件
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 2. 调用业务逻辑
    result = StampService.process_image(str(save_path))

    # 3. 返回结果
    return result