#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置管理模块
负责加载、验证和提供配置信息
"""

import os
import yaml
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class ApiConfig:
    """API配置"""
    api_key: str
    base_url: str
    model: str
    timeout: int


@dataclass
class SecurityConfig:
    """安全配置"""
    confirm_dangerous_commands: bool
    blocked_commands: List[str]
    confirm_patterns: List[str]


@dataclass
class UIConfig:
    """用户界面配置"""
    color_output: bool
    history_file: str
    max_history: int


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str
    file: str
    max_size_mb: int
    backup_count: int


class Config:
    """配置管理类"""
    
    def __init__(self, config_file: str):
        """初始化配置"""
        self.config_file = os.path.abspath(config_file)
        self._raw_config = self._load_config()
        
        self.api = self._parse_api_config()
        self.security = self._parse_security_config()
        self.ui = self._parse_ui_config()
        self.logging = self._parse_logging_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"配置文件不存在: {self.config_file}")
        
        with open(self.config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _parse_api_config(self) -> ApiConfig:
        """解析API配置"""
        api_config = self._raw_config.get('api', {})
        return ApiConfig(
            api_key=api_config.get('api_key', ''),
            base_url=api_config.get('base_url', 'https://api.deepseek.com/v1'),
            model=api_config.get('model', 'deepseek-chat'),
            timeout=api_config.get('timeout', 30)
        )
    
    def _parse_security_config(self) -> SecurityConfig:
        """解析安全配置"""
        security_config = self._raw_config.get('security', {})
        return SecurityConfig(
            confirm_dangerous_commands=security_config.get('confirm_dangerous_commands', True),
            blocked_commands=security_config.get('blocked_commands', []),
            confirm_patterns=security_config.get('confirm_patterns', [])
        )
    
    def _parse_ui_config(self) -> UIConfig:
        """解析用户界面配置"""
        ui_config = self._raw_config.get('ui', {})
        return UIConfig(
            color_output=ui_config.get('color_output', True),
            history_file=ui_config.get('history_file', '~/.linuxagent_history'),
            max_history=ui_config.get('max_history', 1000)
        )
    
    def _parse_logging_config(self) -> LoggingConfig:
        """解析日志配置"""
        logging_config = self._raw_config.get('logging', {})
        return LoggingConfig(
            level=logging_config.get('level', 'INFO'),
            file=logging_config.get('file', '~/.linuxagent.log'),
            max_size_mb=logging_config.get('max_size_mb', 10),
            backup_count=logging_config.get('backup_count', 5)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典"""
        return self._raw_config 