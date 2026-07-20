# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-19
#Description: 手写签名抠图数据模型
#FilePath: /stamp-ai-service/schemas/signature.py
#
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SignatureBox(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(gt=0)
    h: int = Field(gt=0)

    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    label: str = "signature"
    ink_color: str = "black"


class SignatureOutput(BaseModel):
    index: int
    box: SignatureBox

    # 实际输出 PNG 尺寸（可能等于用户指定宽高）
    width: int
    height: int

    # 签名内容在输出画布中的实际占用尺寸（等比缩放后）
    content_width: int
    content_height: int

    file_name: str
    url: Optional[str] = None
    # data:image/png;base64,... 可直接用于前端 <img src>
    base64: Optional[str] = None


class SignatureExtractionResponse(BaseModel):
    request_id: str
    filename: str

    original_width: int
    original_height: int

    processed_width: int
    processed_height: int

    perspective_applied: bool

    # 用户请求的目标尺寸（未指定则为 null）
    target_width: Optional[int] = None
    target_height: Optional[int] = None
    # fit=等比放入画布  fill=等比铺满后居中裁剪
    resize_mode: str = "fit"

    return_type: str = "base64"

    count: int
    signatures: List[SignatureOutput]

    zip_url: Optional[str] = None
    debug_files: List[str] = []
