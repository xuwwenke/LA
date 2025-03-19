#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
用户界面模块
提供与用户交互的命令行界面
"""

import os
import sys
import time
import logging
from typing import Optional, List, Dict, Any, Union, Callable
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.theme import Theme
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from config import Config


class UI:
    """用户界面类，处理与用户的交互"""

    def __init__(self, config: Config):
        """
        初始化UI
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.console = Console()
        self.logger = logging.getLogger(__name__)
        self._setup_theme()

    def _setup_theme(self):
        """设置控制台主题"""
        # 根据配置设置主题
        if self.config.ui.theme == "dark":
            # 深色主题
            theme = Theme({
                "info": "cyan",
                "warning": "yellow",
                "error": "bold red",
                "success": "bold green",
                "command": "yellow",
                "result": "green",
                "highlight": "bold cyan",
            })
        else:
            # 浅色主题
            theme = Theme({
                "info": "blue",
                "warning": "orange3",
                "error": "red",
                "success": "green",
                "command": "dark_orange",
                "result": "dark_green",
                "highlight": "cyan",
            })
        
        self.console = Console(theme=theme)
        
    def show_welcome(self):
        """显示欢迎信息"""
        self.console.print(Panel.fit(
            "[bold]LinuxAgent[/bold] - 你的Linux命令助手\n"
            "输入自然语言描述，获取相应的Linux命令",
            title="欢迎使用",
            border_style="cyan"
        ))
        self.console.print("输入 [bold]exit[/bold] 或 [bold]quit[/bold] 退出程序\n")
        
    def show_thinking(self):
        """显示正在思考的提示"""
        self.console.print("[info]正在思考...[/info]")
        
    def show_result(self, result, command):
        """
        显示命令执行结果
        
        Args:
            result: API分析结果
            command: 执行的命令
        """
        if isinstance(result, str):
            self.console.print(Panel(
                result,
                title="执行结果分析",
                border_style="green"
            ))
            return
            
        explanation = result.get("explanation", "")
        recommendations = result.get("recommendations", [])
        next_steps = result.get("next_steps", [])
        
        content = []
        
        if explanation:
            content.append(f"[bold]分析:[/bold] {explanation}")
            
        if recommendations:
            content.append("\n[bold]建议:[/bold]")
            for i, rec in enumerate(recommendations, 1):
                content.append(f"  {i}. {rec}")
                
        if next_steps:
            content.append("\n[bold]下一步操作:[/bold]")
            for i, step in enumerate(next_steps, 1):
                step_cmd = step.get("command", "")
                step_explanation = step.get("explanation", "")
                
                if step_cmd:
                    content.append(f"  {i}. [yellow]{step_cmd}[/yellow]")
                    if step_explanation:
                        content.append(f"     {step_explanation}")
                elif step_explanation:
                    content.append(f"  {i}. {step_explanation}")
                    
        self.console.print(Panel(
            "\n".join(content),
            title="执行结果分析",
            border_style="green"
        ))
        
    def show_error(self, message):
        """
        显示错误信息
        
        Args:
            message: 错误信息
        """
        self.console.print(f"[error]{message}[/error]")
        
    def get_user_input(self, prompt="请输入你的需求："):
        """
        获取用户输入
        
        Args:
            prompt: 提示信息
            
        Returns:
            用户输入
        """
        try:
            return input(f"{prompt} ")
        except (KeyboardInterrupt, EOFError):
            self.logger.info("用户中断输入")
            return "exit"
            
    def confirm(self, message):
        """
        确认操作
        
        Args:
            message: 确认消息
            
        Returns:
            用户是否确认
        """
        try:
            response = input(f"{message} (y/n) ")
            return response.lower() in ['y', 'yes', '是', '确认', '1', 'true']
        except (KeyboardInterrupt, EOFError):
            self.logger.info("用户中断确认")
            return False
            
    def show_progress(self, message, task_fn, *args, **kwargs):
        """
        显示进度条并执行任务
        
        Args:
            message: 进度条显示的消息
            task_fn: 要执行的任务函数
            args: 传递给任务函数的位置参数
            kwargs: 传递给任务函数的关键字参数
            
        Returns:
            任务函数的返回值
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            transient=True,
        ) as progress:
            task_id = progress.add_task(f"[cyan]{message}[/cyan]", total=None)
            result = task_fn(*args, **kwargs)
            progress.update(task_id, completed=100)
            return result
            
    def show_options(self, title, options):
        """
        显示选项并让用户选择
        
        Args:
            title: 选项标题
            options: 选项列表
            
        Returns:
            用户选择的索引，如果取消则返回None
        """
        self.console.print(f"[bold]{title}[/bold]")
        for i, option in enumerate(options, 1):
            self.console.print(f"  {i}. {option}")
            
        try:
            while True:
                choice = input(f"请选择 (1-{len(options)}, 或q取消): ")
                if choice.lower() in ['q', 'quit', 'cancel', '退出', '取消']:
                    return None
                    
                try:
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(options):
                        return choice_idx
                    else:
                        self.console.print(f"[warning]请输入1-{len(options)}之间的数字[/warning]")
                except ValueError:
                    self.console.print("[warning]请输入有效的数字[/warning]")
        except (KeyboardInterrupt, EOFError):
            self.logger.info("用户中断选择")
            return None
    
    def print_command_execution_info(self, command, start_time, end_time=None, status="进行中"):
        """
        打印命令执行相关信息
        
        Args:
            command: 执行的命令
            start_time: 开始时间
            end_time: 结束时间，如果为None表示命令仍在执行
            status: 命令状态
        """
        if end_time:
            duration = end_time - start_time
            duration_str = f"{duration:.2f}秒"
            if duration > 60:
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                duration_str = f"{minutes}分{seconds}秒"
        else:
            duration_str = f"{time.time() - start_time:.2f}秒"
            
        status_color = {
            "进行中": "yellow",
            "成功": "green",
            "失败": "red",
            "超时": "red",
            "取消": "yellow"
        }.get(status, "white")
        
        self.console.print(f"[bold]命令:[/bold] [yellow]{command}[/yellow]")
        self.console.print(f"[bold]状态:[/bold] [{status_color}]{status}[/{status_color}]")
        self.console.print(f"[bold]耗时:[/bold] {duration_str}")


class ConsoleUI:
    """控制台用户界面"""
    
    def __init__(self, config):
        """
        初始化控制台UI
        
        Args:
            config: UI配置
        """
        self.config = config
        
        self.console = Console()
        
        # 设置提示风格
        self.style = Style.from_dict({
            'prompt': '#00aa00 bold',
            'input': '#ffffff',
        })
        
        history_file = os.path.expanduser(config.history_file)
        history_dir = os.path.dirname(history_file)
        if history_dir and not os.path.exists(history_dir):
            os.makedirs(history_dir)
            
        self.session = PromptSession(
            history=FileHistory(history_file),
            auto_suggest=AutoSuggestFromHistory(),
            style=self.style,
            complete_in_thread=True
        )
        
        # 常用命令提示
        self.common_commands = [
            'help', 'exit', 'clear', 'history', 'config', 
            'ls', 'ps', 'df', 'top', 'systemctl', 'journalctl',
            'find', 'grep', 'awk', 'sed', 'cat', 'tail', 'netstat'
        ]
        
    def welcome(self):
        """显示欢迎信息"""
        logo = r"""
  _      _                      _                     _   
 | |    (_)_ __  _   ___  __   / \   __ _  ___ _ __ | |_ 
 | |    | | '_ \| | | \ \/ /  / _ \ / _` |/ _ \ '_ \| __|
 | |___ | | | | | |_| |>  <  / ___ \ (_| |  __/ | | | |_ 
 |_____|_|_| |_|\__,_/_/\_\/_/   \_\__, |\___|_| |_|\__|
                                    |___/                
        """
        
        version_info = """
┌─────────────────────────────────────────────────────┐
│ [bold green]LinuxAgent[/bold green] - 基于DeepSeek API的智能Linux运维助手    │
│                                                     │
│ [bold]Version:[/bold] [yellow]1.4.1[/yellow]                                      │
└─────────────────────────────────────────────────────┘
        """
        
        self.console.print(f"[bold blue]{logo}[/bold blue]")
        self.console.print(version_info)
        
        self.console.print("\n[bold]输入命令获取帮助:[/bold] [cyan]help[/cyan]")
        self.console.print("[bold]要退出程序，请输入:[/bold] [cyan]exit[/cyan]")
        self.console.print("\n[bold yellow]请描述您需要的Linux运维任务，LinuxAgent将协助您完成。[/bold yellow]\n")
        
    def get_input(self, prompt_text="[LinuxAgent] > ") -> str:
        """
        获取用户输入
        
        Args:
            prompt_text: 提示文本
        
        Returns:
            用户输入
        """
        command_completer = WordCompleter(self.common_commands, ignore_case=True)
        
        user_input = self.session.prompt(
            f"\n{prompt_text} ",
            completer=command_completer
        )
        return user_input.strip()
    
    def show_thinking(self):
        """显示思考中的动画"""
        with self.console.status("[bold green]思考中...[/bold green]", spinner="dots"):
            time.sleep(0.1)  
            # 实际使用时会被阻塞直到AI响应
            
    def show_result(self, result: str, command: Optional[str] = None):
        """
        显示结果
        
        Args:
            result: 结果文本
            command: 执行的命令(如果有)
        """
        if command:
            self.console.print("[bold]执行命令:[/bold]", style="yellow")
            self.console.print(Syntax(command, "bash", theme="monokai"))
            
        if result:
            self.console.print("[bold]执行结果:[/bold]", style="green")
            try:
                self.console.print(Markdown(result))
            except:
                self.console.print(result)
    
    def show_error(self, error_message: str):
        """
        显示错误信息
        
        Args:
            error_message: 错误信息
        """
        self.console.print(f"[bold red]错误:[/bold red] {error_message}")
    
    def confirm(self, message: str) -> bool:
        """
        获取用户确认
        
        Args:
            message: 确认消息
        
        Returns:
            是否确认
        """
        response = self.session.prompt(
            f"{message} [y/N] "
        ).strip().lower()
        return response in ['y', 'yes']
    
    def show_help(self):
        """显示帮助信息"""
        help_text = """
# LinuxAgent 使用帮助

## 基本用法
直接输入自然语言描述您想要执行的操作，例如：
- "查看系统内存使用情况"
- "找出占用CPU最高的5个进程"
- "检查/var/log目录下最近修改的日志文件"

## 内置命令
- `help`: 显示此帮助信息
- `exit`: 退出程序
- `clear`: 清屏
- `history`: 显示历史记录
- `config`: 显示当前配置

## 安全提示
对于潜在危险的操作，LinuxAgent会请求您的确认。
        """
        self.console.print(Markdown(help_text))
    
    def clear_screen(self):
        """清屏"""
        self.console.clear()
        
    def show_history(self, entries: List[str]):
        """
        显示历史记录
        
        Args:
            entries: 历史记录条目
        """
        self.console.print("[bold]历史记录:[/bold]", style="blue")
        for i, entry in enumerate(entries, 1):
            self.console.print(f"{i:3d}. {entry}")
    
    def show_config(self, config: Dict[str, Any]):
        """
        显示配置信息
        
        Args:
            config: 配置字典
        """
        self.console.print("[bold]当前配置:[/bold]", style="blue")
        # 隐藏API密钥
        if 'api' in config and 'api_key' in config['api']:
            config['api']['api_key'] = '********'
            
        import yaml
        config_yaml = yaml.dump(config, default_flow_style=False)
        self.console.print(Syntax(config_yaml, "yaml", theme="monokai"))
    
    def print_command_execution_info(self, command, start_time, end_time=None, status="进行中"):
        """
        打印命令执行相关信息
        
        Args:
            command: 执行的命令
            start_time: 开始时间
            end_time: 结束时间，如果为None表示命令仍在执行
            status: 命令状态
        """
        if end_time:
            duration = end_time - start_time
            duration_str = f"{duration:.2f}秒"
            if duration > 60:
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                duration_str = f"{minutes}分{seconds}秒"
        else:
            duration_str = f"{time.time() - start_time:.2f}秒"
            
        status_color = {
            "进行中": "yellow",
            "成功": "green",
            "失败": "red",
            "超时": "red",
            "取消": "yellow"
        }.get(status, "white")
        
        self.console.print(f"[bold]命令:[/bold] [yellow]{command}[/yellow]")
        self.console.print(f"[bold]状态:[/bold] [{status_color}]{status}[/{status_color}]")
        self.console.print(f"[bold]耗时:[/bold] {duration_str}") 
