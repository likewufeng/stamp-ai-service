# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 09:39:42
#LastEditTime: 2026-07-20 13:48:16
#LastEditors: WuFeng <763467339@qq.com>
#Description: 服务器入口
#FilePath: /stamp-ai-service/app.py
#Copyright 版权声明
#
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from starlette.staticfiles import StaticFiles

from api.health import router as health_router
from api.signature import router as signature_router
from api.stamp import router as stamp_router
from config import (
    APP_NAME,
    APP_VERSION,
    LOG_DIR,
    OUTPUT_DIR,
)
from utils.cleanup import cleanup_service


logger.add(
    LOG_DIR / "service.log",
    rotation="50 MB",
    retention="30 days",
    encoding="utf-8",
    enqueue=True,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动后台清理任务
    cleanup_service.start()
    try:
        # 启动时先跑一轮，尽快回收历史垃圾文件
        cleanup_service.run_once()
    except Exception:
        logger.exception("启动时文件清理失败")

    yield

    cleanup_service.stop()


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "印章 / 手写签名检测、抠图与透明 PNG 生成服务"
    ),
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount(
    "/outputs",
    StaticFiles(
        directory=str(OUTPUT_DIR),
    ),
    name="outputs",
)


app.include_router(health_router)
app.include_router(stamp_router)
app.include_router(signature_router)


@app.get("/")
def root():
    return {
        "name": APP_NAME,
        "version": APP_VERSION,
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    reload_enabled = (
        os.getenv(
            "APP_RELOAD",
            "false",
        ).lower()
        == "true"
    )

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(
            os.getenv("APP_PORT", "8000")
        ),
        reload=reload_enabled,
    )
