# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 09:39:42
#LastEditTime: 2026-07-22 10:17:40
#LastEditors: WuFeng <763467339@qq.com>
#Description: 服务器入口
#FilePath: /stamp-ai-service/app.py
#Copyright 版权声明
#
# ──────────────────────────────────────────────
# 必须在最开始加载 .env，确保后续导入 config 时环境变量已生效
# 本地开发：读取项目根目录 .env
# Docker/生产：docker-compose 已通过 env_file 注入，load_dotenv 会静默跳过
# ──────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()  # 自动查找并加载 .env 文件
except ImportError:
    pass  # 生产环境未装 python-dotenv 时忽略

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
    LOG_RETENTION_DAYS,
    OUTPUT_DIR,
)
from utils.cleanup import cleanup_service


logger.add(
    LOG_DIR / "service.log",
    rotation="50 MB",
    retention=f"{LOG_RETENTION_DAYS} days",
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
            # local bare-metal default; Docker still uses container 8000
            os.getenv("APP_PORT", "18080")
        ),
        reload=reload_enabled,
    )
