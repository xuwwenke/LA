#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
核心代理模块
负责协调用户界面、DeepSeek API和命令执行组件
"""

import os
import sys
import time
import logging
import re
from typing import List, Dict, Any, Optional, Tuple

from .config import Config
from .ui import ConsoleUI
from .deepseek_api import DeepSeekAPI
from .command_executor import CommandExecutor


class Agent:
    """LinuxAgent代理类"""
    
    def __init__(self, config: Config, ui: ConsoleUI, logger=None):
        """初始化代理"""
        self.config = config
        self.ui = ui
        self.logger = logger or logging.getLogger("agent")
        
        self.api = DeepSeekAPI(config.api, logger=self.logger)
        self.executor = CommandExecutor(config.security, logger=self.logger)
        self.history = []
        
        self._check_api_availability()
    
    def _check_api_availability(self):
        """检查API是否可用"""
        self.logger.info("检查DeepSeek API可用性")
        
        if not self.api.api_key:
            self.logger.warning("未设置DeepSeek API密钥")
            self.ui.show_error("未设置DeepSeek API密钥，请在配置文件中设置")
            return False
        
        is_available = self.api.is_api_available()
        if not is_available:
            self.logger.error("DeepSeek API不可用")
            self.ui.show_error("DeepSeek API连接失败，请检查网络和API密钥")
            return False
            
        self.logger.info("DeepSeek API可用")
        return True
    
    def _handle_special_commands(self, user_input: str) -> bool:
        """处理特殊命令"""
        if user_input.lower() in ["exit", "quit", "bye"]:
            self.logger.info("用户请求退出")
            return True
            
        elif user_input.lower() == "help":
            self.logger.info("显示帮助信息")
            self.ui.show_help()
            return True
            
        elif user_input.lower() == "clear":
            self.logger.info("清屏")
            self.ui.clear_screen()
            return True
            
        elif user_input.lower() == "history":
            self.logger.info("显示历史记录")
            history_entries = [entry["user_input"] for entry in self.history]
            self.ui.show_history(history_entries)
            return True
            
        elif user_input.lower() == "config":
            self.logger.info("显示配置信息")
            self.ui.show_config(self.config.to_dict())
            return True
            
        elif user_input.lower().startswith("edit "):
            parts = user_input.split(" ", 2)
            file_path = parts[1] if len(parts) > 1 else ""
            editor = parts[2] if len(parts) > 2 else "vim"
            
            if not file_path:
                self.ui.show_error("请指定要编辑的文件路径")
                return True
                
            self.logger.info(f"使用 {editor} 编辑文件: {file_path}")
            self.ui.console.print(f"[bold]正在使用 {editor} 编辑文件: [/bold][yellow]{file_path}[/yellow]")
            
            stdout, stderr, return_code = self.executor.execute_file_editor(file_path, editor)
            
            if return_code == 0:
                self.ui.console.print("[bold green]文件编辑完成[/bold green]")
            else:
                self.ui.show_error(f"编辑文件时出错: {stderr}")
                
            return True
            
        return False
    
    def process_user_input(self, user_input: str) -> None:
        """处理用户输入"""
        self.logger.info(f"处理用户输入: {user_input}")
        
        self.history.append({
            "user_input": user_input,
            "timestamp": time.time()
        })
        
        self.ui.show_thinking()
        
        try:
            system_info = self.executor.get_system_info()           
            simple_commands = ["ls", "pwd", "cd", "cat", "echo", "mkdir", "touch", "cp", "mv", "rm", "ps", "df", "du"]
            command_parts = user_input.split()
            if command_parts and command_parts[0] in simple_commands:
                # 直接执行简单系统命令，无需调用API
                self.logger.info(f"识别为简单系统命令: {user_input}")
                command = user_input
                explanation = f"执行{command_parts[0]}命令"
                self.ui.console.print(f"[bold]理解:[/bold] {explanation}")
                self.ui.console.print(f"[bold]要执行的命令:[/bold] [yellow]{command}[/yellow]")
                
                is_interactive = self.executor._is_interactive_command(command)
                is_safe, unsafe_reason = self.executor.is_command_safe(command)
                
                if not is_safe and self.config.security.confirm_dangerous_commands:
                    confirmation_message = f"此命令可能有风险: {unsafe_reason}。确认执行?"
                    if not self.ui.confirm(confirmation_message):
                        self.logger.info("用户取消执行危险命令")
                        self.ui.console.print("[bold red]已取消执行[/bold red]")
                        return
                
                self.ui.console.print("[bold cyan]正在执行命令，这可能需要一些时间...[/bold cyan]")
                with self.ui.console.status("[bold green]命令执行中...[/bold green]", spinner="dots"):
                    stdout, stderr, return_code = self.executor.execute_command(command)
                
                if return_code == 0:
                    self.ui.console.print("[bold green]命令执行成功！[/bold green]")
                    self.ui.show_result(stdout, command)
                else:
                    self.logger.warning(f"命令执行失败: {stderr}")
                    self.ui.console.print("[bold red]命令执行失败[/bold red]")
                    self.ui.show_result(stderr, command)
                return
            
            parsed_command = self._parse_create_edit_request(user_input)
            if parsed_command:
                self.logger.info(f"执行直接编辑/创建操作: {parsed_command}")
                self._execute_edit_operation(parsed_command)
                return
            
            interactive_command = self._parse_interactive_command(user_input)
            if interactive_command:
                self.logger.info(f"直接执行交互式命令: {interactive_command}")
                self._execute_interactive_operation(interactive_command)
                return
            
            result = self.api.get_command_for_task(user_input, system_info)
            
            command = result.get("command", "")
            explanation = result.get("explanation", "")
            dangerous = result.get("dangerous", False)
            reason_if_dangerous = result.get("reason_if_dangerous", "")
            
            if not command:
                self.logger.warning("API未返回有效命令")
                self.ui.show_error("无法理解您的请求或无法生成对应的命令")
                return
            
            if len(command) > 1000:
                self.logger.warning(f"生成的命令过长，可能不是有效命令: {command[:100]}...")
                self.ui.show_error("生成的命令异常，无法执行。请尝试用更简洁的方式描述您的需求。")
                return
                
            suspicious_starts = ["###", "##", "#", "解释:", "命令目的:", "安全性:", "是否是危险命令:"]
            if any(command.startswith(prefix) for prefix in suspicious_starts):
                self.logger.warning(f"生成的命令可能是解释文本，而非实际命令: {command}")
                self.ui.show_error("生成的命令格式异常，无法执行。请重新描述您的需求。")
                return
                
            self.logger.info(f"生成命令: {command}")
            
            if self._is_file_creation_command(command):
                file_path = self._extract_file_path(command)
                if file_path:
                    self.ui.console.print(f"[bold]理解:[/bold] {explanation}")
                    self.ui.console.print(f"[bold]检测到文件创建/编辑命令，将使用交互式编辑器打开文件[/bold]")
                    
                    self._ensure_directory_exists(file_path)
                    
                    editor = self._get_preferred_editor()
                    self._execute_edit_operation(f"{editor} {file_path}")
                    return
            
            is_complex_command = self._is_complex_command(command)
            
            is_safe, unsafe_reason = self.executor.is_command_safe(command)
            needs_confirmation = False
            
            if not is_safe:
                needs_confirmation = True
                self.logger.warning(f"命令不安全: {unsafe_reason}")
            elif dangerous:
                needs_confirmation = True
                unsafe_reason = reason_if_dangerous
                self.logger.warning(f"命令可能有风险: {reason_if_dangerous}")
            
            self.ui.console.print(f"[bold]理解:[/bold] {explanation}")
            self.ui.console.print(f"[bold]要执行的命令:[/bold] [yellow]{command}[/yellow]")
            
            is_interactive = self.executor._is_interactive_command(command)
            
            if is_interactive:
                if "vim" in command or "vi" in command or "nano" in command or "emacs" in command:
                    self.ui.console.print("[bold cyan]这是一个文本编辑命令，将打开编辑器供您交互操作。[/bold cyan]")
                    self.ui.console.print("[bold cyan]完成编辑后，请保存并退出编辑器继续操作。[/bold cyan]")
                else:
                    self.ui.console.print("[bold cyan]这是一个交互式命令，将直接在终端中执行...[/bold cyan]")
            
            if is_complex_command and '&&' in command and not is_interactive:
                confirmation_message = "这是一个复杂命令，可能需要较长时间执行。是否拆分为多个命令分步执行？"
                if self.ui.confirm(confirmation_message):
                    self.logger.info("用户选择拆分复杂命令")
                    commands = self._split_complex_command(command)
                    self._execute_commands_sequence(commands, explanation)
                    return
            
            if needs_confirmation and self.config.security.confirm_dangerous_commands:
                confirmation_message = f"此命令可能有风险: {unsafe_reason}。确认执行?"
                if not self.ui.confirm(confirmation_message):
                    self.logger.info("用户取消执行危险命令")
                    self.ui.console.print("[bold red]已取消执行[/bold red]")
                    return
            
            self.ui.console.print("[bold cyan]正在执行命令，这可能需要一些时间...[/bold cyan]")
            
            if is_interactive:
                stdout, stderr, return_code = self.executor.execute_command(command)
            else:
                with self.ui.console.status("[bold green]命令执行中...[/bold green]", spinner="dots"):
                    stdout, stderr, return_code = self.executor.execute_command(command)
            
            if is_interactive:
                if return_code == 0:
                    self.ui.console.print("[bold green]交互式命令执行完成[/bold green]")
                else:
                    self.ui.show_error(f"交互式命令执行失败: {stderr}")
                return
                
            if return_code == 0:
                self.ui.console.print("[bold green]命令执行成功！正在分析结果...[/bold green]")
                analysis = self.api.analyze_command_output(command, stdout, stderr)
                self.ui.show_result(analysis, command)
            else:
                self.logger.warning(f"命令执行失败: {stderr}")
                self.ui.console.print("[bold yellow]命令执行返回非零状态，正在分析问题...[/bold yellow]")
                analysis = self.api.analyze_command_output(command, stdout, stderr)
                self.ui.show_result(analysis, command)
                
        except Exception as e:
            self.logger.error(f"处理用户输入时出错: {e}", exc_info=True)
            self.ui.show_error(f"处理请求时出错: {e}")
    
    def _is_complex_command(self, command: str) -> bool:
        """判断命令是否复杂"""
        if command.count('&&') > 2 or command.count(';') > 2:
            return True
            
        pkg_managers = ['dnf', 'yum', 'apt', 'apt-get', 'pacman', 'zypper']
        pkg_operations = ['update', 'upgrade', 'install']
        
        for pm in pkg_managers:
            for op in pkg_operations:
                if f"{pm} {op}" in command:
                    return True
                    
        return False
    
    def _split_complex_command(self, command: str) -> List[str]:
        """拆分复杂命令为多个简单命令"""
        if '&&' in command:
            return [cmd.strip() for cmd in command.split('&&')]
        elif ';' in command:
            return [cmd.strip() for cmd in command.split(';')]
        else:
            return [command]
    
    def _execute_commands_sequence(self, commands: List[str], explanation: str) -> None:
        """按顺序执行多个命令"""
        self.ui.console.print(f"[bold]将按以下顺序执行命令:[/bold]")
        for i, cmd in enumerate(commands, 1):
            self.ui.console.print(f"{i}. [yellow]{cmd}[/yellow]")
            
        total_commands = len(commands)
        results = []
        
        for i, cmd in enumerate(commands, 1):
            self.ui.console.print(f"\n[bold]执行步骤 {i}/{total_commands}:[/bold] [yellow]{cmd}[/yellow]")
            
            is_safe, unsafe_reason = self.executor.is_command_safe(cmd)
            if not is_safe and self.config.security.confirm_dangerous_commands:
                confirmation_message = f"此命令可能有风险: {unsafe_reason}。确认执行?"
                if not self.ui.confirm(confirmation_message):
                    self.ui.console.print("[bold red]跳过此步骤[/bold red]")
                    results.append((cmd, "", "用户取消执行", 1))
                    continue
            
            start_time = time.time()
            with self.ui.console.status(f"[bold green]执行步骤 {i}/{total_commands}...[/bold green]", spinner="dots"):
                stdout, stderr, return_code = self.executor.execute_command(cmd)
            end_time = time.time()
            
            status = "成功" if return_code == 0 else "失败"
            self.ui.print_command_execution_info(cmd, start_time, end_time, status)
            
            if return_code == 0:
                self.ui.console.print(f"[bold green]步骤 {i} 执行成功[/bold green]")
                if stdout:
                    self.ui.console.print("[bold]输出:[/bold]")
                    max_output_lines = 20
                    output_lines = stdout.splitlines()
                    if len(output_lines) > max_output_lines:
                        shown_output = "\n".join(output_lines[:10] + ["...省略中间内容..."] + output_lines[-10:])
                        self.ui.console.print(shown_output)
                        self.ui.console.print(f"[dim](输出共 {len(output_lines)} 行，仅显示部分内容)[/dim]")
                    else:
                        self.ui.console.print(stdout)
            else:
                self.ui.console.print(f"[bold red]步骤 {i} 执行失败[/bold red]")
                if stderr:
                    self.ui.console.print("[bold red]错误信息:[/bold red]")
                    self.ui.console.print(stderr)
            
            results.append((cmd, stdout, stderr, return_code))
            
            if return_code != 0 and i < total_commands:
                if not self.ui.confirm("上一步执行失败，是否继续执行后续步骤?"):
                    self.ui.console.print("[bold yellow]用户中止后续步骤[/bold yellow]")
                    break
        
        self.ui.console.print("\n[bold]所有步骤执行完毕，正在分析结果...[/bold]")
        all_stdout = "\n".join([f"命令 {i+1}: {res[0]}\n输出:\n{res[1]}\n" for i, res in enumerate(results)])
        all_stderr = "\n".join([f"命令 {i+1} 错误:\n{res[2]}\n" if res[2] else "" for i, res in enumerate(results)])
        
        analysis = self.api.analyze_command_output("; ".join([r[0] for r in results]), all_stdout, all_stderr)
        self.ui.show_result(analysis, explanation)
    
    def _parse_interactive_command(self, user_input: str) -> Optional[str]:
        """解析常见交互式命令模式"""
        edit_patterns = [
            r'使用\s+(\w+)\s+编辑\s+([^\s]+)(\s+文件)?',
            r'用\s+(\w+)\s+打开\s+([^\s]+)(\s+文件)?',
            r'编辑\s+([^\s]+)(\s+文件)?(\s+用\s+(\w+))?'
        ]
        
        for pattern in edit_patterns:
            match = re.search(pattern, user_input)
            if match:
                groups = match.groups()
                if pattern == edit_patterns[0] or pattern == edit_patterns[1]:
                    editor = groups[0]
                    file_path = groups[1]
                elif pattern == edit_patterns[2]:
                    file_path = groups[0]
                    editor = groups[3] if groups[3] else "vim"
                else:
                    continue
                    
                if editor not in ["vim", "vi", "nano", "emacs"]:
                    continue
                    
                return f"{editor} {file_path}"
        
        for cmd in self.executor.interactive_commands:
            if user_input.startswith(cmd + " ") or user_input == cmd:
                return user_input
                
        return None
    
    def _execute_edit_operation(self, command: str) -> None:
        """执行编辑操作"""
        parts = command.split()
        file_path = parts[-1]
        editor = parts[-2] if len(parts) > 1 else "vim"
        
        self.ui.console.print(f"[bold]正在使用 {editor} 编辑文件: [/bold][yellow]{file_path}[/yellow]")
        
        if file_path.endswith('.html'):
            if 'login' in file_path.lower() or '登录' in file_path or '注册' in file_path:
                self._get_template_suggestion(file_path, "登录注册")
        
        stdout, stderr, return_code = self.executor.execute_file_editor(file_path, editor.split('/')[-1])
        
        if return_code == 0:
            self.ui.console.print("[bold green]文件编辑完成[/bold green]")
            
            if file_path.endswith('.html'):
                if "nginx" in file_path or file_path.startswith("/usr/share/nginx"):
                    if self.ui.confirm("是否重启Nginx服务以应用更改？"):
                        self.ui.console.print("[bold cyan]正在重启Nginx服务...[/bold cyan]")
                        restart_stdout, restart_stderr, restart_code = self.executor.execute_command("sudo systemctl restart nginx")
                        if restart_code == 0:
                            self.ui.console.print("[bold green]Nginx服务已重启[/bold green]")
                        else:
                            self.ui.show_error(f"重启Nginx服务失败: {restart_stderr}")
        else:
            self.ui.show_error(f"编辑文件时出错: {stderr}")
    
    def _get_template_suggestion(self, file_path: str, file_type: str) -> None:
        """从DeepSeek API获取模板建议"""
        try:
            system_info = self.executor.get_system_info()
            prompt = f"需要创建{file_type}类型的文件：{file_path}，提供简洁的编辑建议。"
            response = self.api.get_template_suggestion(prompt, system_info)
            
            if response and "suggestion" in response:
                self.ui.console.print(f"[bold]编辑建议:[/bold] {response['suggestion']}")
        except Exception as e:
            self.logger.error(f"获取模板建议失败: {e}")
    
    def _execute_interactive_operation(self, command: str) -> None:
        """执行交互式操作"""
        self.ui.console.print(f"[bold]执行交互式命令:[/bold] [yellow]{command}[/yellow]")
        
        is_editor = any(editor in command.split()[0] for editor in ["vim", "vi", "nano", "emacs"])
        if is_editor:
            file_path = command.split()[-1]
            if file_path.endswith('.html'):
                file_type = "HTML页面"
                if 'login' in file_path.lower() or '登录' in file_path or '注册' in file_path:
                    file_type = "登录注册页面"
                self._get_template_suggestion(file_path, file_type)
        
        stdout, stderr, return_code = self.executor.execute_command(command)
        
        if return_code == 0:
            self.ui.console.print("[bold green]命令执行成功[/bold green]")
            
            if is_editor:
                file_path = command.split()[-1]
                if file_path.endswith('.html'):
                    if "nginx" in file_path or "/var/www/" in file_path or "/usr/share/nginx/" in file_path:
                        if self.ui.confirm("是否重启Nginx服务以应用更改？"):
                            self.ui.console.print("[bold cyan]正在重启Nginx服务...[/bold cyan]")
                            restart_stdout, restart_stderr, restart_code = self.executor.execute_command("sudo systemctl restart nginx")
                            if restart_code == 0:
                                self.ui.console.print("[bold green]Nginx服务已重启[/bold green]")
                            else:
                                self.ui.show_error(f"重启Nginx服务失败: {restart_stderr}")
        else:
            self.ui.show_error(f"命令执行失败: {stderr}")
            
    def _parse_create_edit_request(self, user_input: str) -> Optional[str]:
        """解析创建/编辑文件的请求"""
        web_page_patterns = [
            r'创建.*(?:网页|页面|HTML|html|登录页|注册页)',
            r'制作.*(?:网页|页面|HTML|html|登录页|注册页)',
            r'开发.*(?:网页|页面|HTML|html|登录页|注册页)',
            r'编写.*(?:网页|页面|HTML|html|登录页|注册页)'
        ]
        
        for pattern in web_page_patterns:
            if re.search(pattern, user_input):
                file_path_match = re.search(r'保存到\s+([^\s]+)', user_input)
                if file_path_match:
                    file_path = file_path_match.group(1)
                else:
                    file_path = "/var/www/html/index.html"
                
                if "nginx" in user_input.lower():
                    file_path = "/usr/share/nginx/html/index.html"
                
                editor = "vim"
                if "nano" in user_input.lower():
                    editor = "nano"
                elif "emacs" in user_input.lower():
                    editor = "emacs"
                
                return f"sudo {editor} {file_path}"
        
        return None
    
    def _is_file_creation_command(self, command: str) -> bool:
        """检查命令是否是创建文件的命令"""
        creation_patterns = [
            r'echo .* > .+\.html',
            r'cat > .+\.html',
            r'touch .+\.html',
            r'printf .* > .+\.html'
        ]
        
        return any(re.search(pattern, command) for pattern in creation_patterns)
    
    def _extract_file_path(self, command: str) -> Optional[str]:
        """从命令中提取文件路径"""
        redirect_match = re.search(r'> ([^\s;|&]+)', command)
        if redirect_match:
            return redirect_match.group(1)
            
        touch_match = re.search(r'touch ([^\s;|&]+)', command)
        if touch_match:
            return touch_match.group(1)
            
        return None
        
    def _ensure_directory_exists(self, file_path: str) -> None:
        """确保文件所在目录存在"""
        try:
            dir_path = os.path.dirname(file_path)
            if dir_path and not os.path.exists(dir_path):
                self.executor.execute_command(f"sudo mkdir -p {dir_path}")
        except Exception as e:
            self.logger.error(f"创建目录失败: {e}")
            
    def _get_preferred_editor(self) -> str:
        """获取首选编辑器"""
        editors = ["vim", "nano", "vi", "emacs"]
        
        if "EDITOR" in os.environ:
            editor = os.environ["EDITOR"]
            if any(ed in editor for ed in editors):
                return editor
                
        return "vim"
    
    def run(self):
        """运行代理主循环"""
        self.logger.info("启动LinuxAgent代理")
        
        # 启动时清屏
        self.ui.clear_screen()
        self.ui.welcome()
        
        while True:
            try:
                user_input = self.ui.get_input()
                
                if not user_input:
                    continue
                
                if self._handle_special_commands(user_input):
                    if user_input.lower() in ["exit", "quit", "bye"]:
                        break
                    continue
                
                self.process_user_input(user_input)
                
            except KeyboardInterrupt:
                self.logger.info("用户中断")
                self.ui.console.print("\n[bold yellow]操作已中断[/bold yellow]")
                
            except Exception as e:
                self.logger.error(f"主循环异常: {e}", exc_info=True)
                self.ui.show_error(f"发生错误: {e}")
        
        self.logger.info("LinuxAgent代理已退出") 