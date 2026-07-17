# -*- coding: utf-8 -*-
#Author: WuFeng <763467339@qq.com>
#Date: 2026-07-17 10:11:46
#LastEditTime: 2026-07-17 10:11:46
#LastEditors: WuFeng <763467339@qq.com>
#Description: 响应格式
#FilePath: /stamp-ai-service/utils/response.py
#Copyright 版权声明
#
def success(data=None):

    return {
        "code":0,
        "message":"success",
        "data":data
    }


def fail(msg):

    return {
        "code":-1,
        "message":msg
    }