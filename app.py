# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 09:39:42
#LastEditTime: 2026-07-17 09:39:53
#LastEditors: WuFeng <763467339@qq.com>
#Description: 服务器入口
#FilePath: /stamp-ai-service/app.py
#Copyright 版权声明
#
from fastapi import FastAPI

from api.health import router as health_router
from api.stamp import router as stamp_router

app = FastAPI(
    title="Stamp AI Service",
    version="1.0.0",
    description="印章识别与透明PNG生成"
)

app.include_router(health_router)
app.include_router(stamp_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )