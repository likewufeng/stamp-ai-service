# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:45:35
#LastEditTime: 2026-07-17 15:24:10
#LastEditors: WuFeng <763467339@qq.com>
#Description: 单例管理
#FilePath: /stamp-ai-service/core/model_manager.py
#Copyright 版权声明
#
from core.detector_factory import DetectorFactory


class ModelManager:

    _instance = None

    def __new__(cls):

        if cls._instance is None:

            cls._instance = super().__new__(cls)

            cls._instance.detector = DetectorFactory.create_detector()

        return cls._instance


model_manager = ModelManager()