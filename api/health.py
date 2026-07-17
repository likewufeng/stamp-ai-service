# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:12:15
#LastEditTime: 2026-07-17 10:12:15
#LastEditors: WuFeng <763467339@qq.com>
#Description: 健康检查接口
#FilePath: /stamp-ai-service/api/health.py
#Copyright 版权声明
#
from fastapi import APIRouter

router = APIRouter(prefix="/api")


@router.get("/health")
def health():

    return {
        "status":"ok"
    }