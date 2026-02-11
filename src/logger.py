"""
Centralized Logging System
==========================
ระบบ logging ที่ทำงานในทั้ง app และ scripts
บันทึก logs ลงไฟล์ + console
"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from src.paths import ProjectPaths


class LoggerSetup:
    """สร้างและจัดการ logger"""
    
    _loggers = {}
    
    @classmethod
    def setup_logger(cls, name, level=logging.INFO):
        """
        สร้าง logger พร้อม file + console handlers
        
        Args:
            name: ชื่อ logger (เช่น 'app', 'video_gen', 'watcher')
            level: logging level (DEBUG, INFO, WARNING, ERROR)
        
        Returns:
            logger object
        """
        # ถ้าสร้างแล้วให้ return เดิม
        if name in cls._loggers:
            return cls._loggers[name]
        
        # สร้าง logger
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # ล้าง handlers เดิม (ถ้ามี)
        logger.handlers.clear()
        
        # สร้าง log directory
        log_dir = ProjectPaths.LOGS
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # สร้าง log file path
        log_file = log_dir / f"{name}.log"
        
        # Formatter
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File Handler - บันทึกลงไฟล์
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,  # เก็บ 5 ไฟล์ เก่า
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Console Handler - แสดงใน terminal
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        
        # Console formatter (สั้นกว่า)
        console_formatter = logging.Formatter(
            fmt='%(levelname)s - %(name)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # เก็บ logger ไว้ใช้ต่อ
        cls._loggers[name] = logger
        
        return logger


# Create loggers for different modules
def get_logger(name):
    """ได้ logger ตามชื่อ"""
    return LoggerSetup.setup_logger(name)


# Shortcuts
app_logger = LoggerSetup.setup_logger('app')
video_logger = LoggerSetup.setup_logger('video_generator')
watcher_logger = LoggerSetup.setup_logger('folder_watcher')
import_logger = LoggerSetup.setup_logger('batch_import')
database_logger = LoggerSetup.setup_logger('database')


if __name__ == "__main__":
    # Test logger
    logger = LoggerSetup.setup_logger('test')
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    print("\n✅ Logger setup successful")
    print(f"Logs saved to: {ProjectPaths.LOGS}")
