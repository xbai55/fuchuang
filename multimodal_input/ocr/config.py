"""
OCR模块配置文件
"""

# OCR配置参数
OCR_CONFIG = {
    'use_angle_cls': True,  # 是否使用角度分类器
    'lang': 'ch',           # 识别语言: ch(中文), en(英文), 其他支持的语言
    'det_model_dir': '',    # 文本检测模型路径
    'rec_model_dir': '',    # 文本识别模型路径
    'cls_model_dir': '',    # 方向分类模型路径
    'precision': 'fp32',    # 计算精度
    'gpu': False,           # 是否使用GPU
    'max_side_len': 960     # 图像最大边长
}

# 服务器配置
SERVER_CONFIG = {
    'host': '127.0.0.1',
    'port': 8002,
    'workers': 1,
    'timeout': 300
}

# 日志配置
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s %(levelname)s [%(name)s] %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# OCR处理相关常量
PROCESSING_CONSTANTS = {
    'MIN_CONFIDENCE': 0.5,      # 最小置信度阈值
    'MAX_FRAMES_PER_TASK': 50,  # 单次任务最大处理帧数
    'TEMP_DIR': './temp_ocr'    # 临时文件目录
}