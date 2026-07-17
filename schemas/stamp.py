# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:47:24
#LastEditTime: 2026-07-17 15:47:39
#LastEditors: WuFeng <763467339@qq.com>
#Description: 数据模型
#FilePath: /stamp-ai-service/schemas/stamp.py
#Copyright 版权声明
#
from typing import List, Optional

from pydantic import BaseModel, Field


class StampBox(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(gt=0)
    h: int = Field(gt=0)

    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    label: str = "stamp"
    color: str = "unknown"


class StampOutput(BaseModel):
    index: int
    box: StampBox

    width: int
    height: int

    file_name: str
    url: str


class StampExtractionResponse(BaseModel):
    request_id: str
    filename: str

    original_width: int
    original_height: int

    processed_width: int
    processed_height: int

    perspective_applied: bool

    count: int
    stamps: List[StampOutput]

    zip_url: Optional[str] = None
    debug_files: List[str] = []