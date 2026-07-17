# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:45:35
#LastEditTime: 2026-07-17 15:24:58
#LastEditors: WuFeng <763467339@qq.com>
#Description: 业务管理
#FilePath: /stamp-ai-service/core/service.py
#Copyright 版权声明
#
from pathlib import Path

import cv2

from core.model_manager import model_manager
from core.processors.document_processor import DocumentProcessor
from schemas.stamp import StampDetectionResponse


class StampService:

    def __init__(self):

        self.processor = DocumentProcessor()

    def process_image(
        self,
        file_path: str,
        debug=False
    ):

        image = cv2.imread(file_path)

        if image is None:
            raise ValueError("读取图片失败")

        image = self.processor.process(image)

        stamps = model_manager.detector.detect_image(
            image=image,
            debug=debug
        )

        return StampDetectionResponse(
            filename=Path(file_path).name,
            stamps=stamps
        )


stamp_service = StampService()