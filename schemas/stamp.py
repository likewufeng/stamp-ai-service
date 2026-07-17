# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:47:24
#LastEditTime: 2026-07-17 15:25:36
#LastEditors: WuFeng <763467339@qq.com>
#Description: 数据模型
#FilePath: /stamp-ai-service/schemas/stamp.py
#Copyright 版权声明
#
from typing import List

from pydantic import BaseModel


class StampBox(BaseModel):

    x: int
    y: int
    w: int
    h: int

    confidence: float = 1.0

    label: str = "stamp"

    color: str = "unknown"


class StampDetectionResponse(BaseModel):

    filename: str

    stamps: List[StampBox]