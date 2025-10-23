#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sora视频生成器 - 交互式命令行应用
支持多线程视频生成、自动重试、进度监控和文件下载
"""

import os
import sys
import time
import json
import requests
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re

# 太多的重试仍然失败（总共30次以上），说明根本过不了审，没必要再使用对应的图片和提示词继续尝试生成
max_retries = 5  # 最大重试次数，建议值为 3-10
max_workers = 5  # 同时进行的最大任务数量，不建议超过 10
max_video_count = 15 # 最大队列数量，无限制，但是你的积分要够用

class VideoGeneratorApp:
    def __init__(self):
        """初始化应用"""
        self.api_key = None
        self.base_url = "https://grsai.dakka.com.cn"  # 国内直连节点
        self.credits = 0  # 积分余额
        self.model_status = False  # 模型状态
        self.tasks = []  # 任务列表
        self.download_dir = Path("download")  # 下载目录
        self.download_dir.mkdir(exist_ok=True)  # 创建下载目录
        self.lock = threading.RLock()  # 可重入锁，用于保护共享数据
        self.is_running = True  # 程序运行状态标志
        self.config_file = Path("config.json")  # 配置文件路径
        self.last_api_call_time = 0  # 记录上次API调用时间，用于控制频率

    @staticmethod
    def clear_screen():
        """清屏函数 - 跨平台兼容"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print("\n")

    @staticmethod
    def print_header(title):
        """打印标题 - 使用ASCII艺术字符美化"""
        print("╔" + "═" * 58 + "╗")
        print("║" + f"🎬 {title}".center(54) + " ")
        print("╚" + "═" * 58 + "╝")
        print()

    @staticmethod
    def print_success(message):
        """打印成功信息 - 使用绿色对勾符号"""
        print(f"【✓】{message}")

    @staticmethod
    def print_error(message):
        """打印错误信息 - 使用红色叉号符号"""
        print(f"【✗】{message}")

    @staticmethod
    def print_warning(message):
        """打印警告信息 - 使用黄色感叹号符号"""
        print(f"【!】{message}")

    @staticmethod
    def print_info(message):
        """打印信息 - 使用蓝色信息符号"""
        print(f"【i】{message}")

    def validate_api_key(self, api_key):
        """
        验证API密钥格式

        Args:
            api_key: 用户输入的API密钥

        Returns:
            tuple: (是否有效, 错误信息)
        """
        if not api_key:
            return False, "API密钥不能为空"
        if not api_key.startswith("sk-"):
            return False, "API密钥格式错误，应以'sk-'开头"
        if len(api_key) < 10:
            return False, "API密钥长度过短，请检查是否正确"
        # 移除可能的空格
        self.api_key = api_key.strip()
        return True, "API密钥格式正确"

    @staticmethod
    def validate_url(url):
        """
        验证URL格式

        Args:
            url: 图片URL

        Returns:
            bool: URL是否有效
        """
        if not url:
            return True  # 空URL是允许的（选填）

        # 基本的URL格式验证
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        return bool(url_pattern.match(url))

    def load_config(self):
        """
        从配置文件加载API密钥

        Returns:
            bool: 加载是否成功
        """
        try:
            if not self.config_file.exists():
                self.print_error(f"配置文件 {self.config_file} 不存在，正在尝试创建配置文件。")
                self.create_sample_config()
                self.print_info("已创建配置文件【config.json】，请在配置文件中添加API密钥，格式如下:")
                self.print_info('{"api_key": "sk-your-api-key-here"}')
                return False

            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            api_key = config.get('api_key')
            if not api_key:
                self.print_error("配置文件中未找到api_key字段")
                return False

            valid, message = self.validate_api_key(api_key)
            if not valid:
                self.print_error(f"配置文件中的API密钥无效: {message}")
                return False

            self.api_key = api_key
            self.print_success("API密钥已从配置文件加载")
            return True

        except json.JSONDecodeError:
            self.print_error("配置文件格式错误，应为有效的JSON格式")
            return False
        except Exception as e:
            self.print_error(f"读取配置文件时发生错误: {str(e)}")
            return False

    def get_credits(self):
        """
        获取积分余额

        Returns:
            bool: 获取是否成功
        """
        try:
            # 确保API密钥不为空
            if not self.api_key:
                self.print_error("API密钥为空，无法获取积分")
                return False

            url = f"{self.base_url}/client/common/getCredits?apikey={self.api_key}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    self.credits = data["data"]["credits"]
                    return True
                else:
                    error_msg = data.get('msg', '未知错误')
                    self.print_error(f"获取积分失败: {error_msg}")
                    return False
            else:
                self.print_error(f"HTTP错误: {response.status_code}")
                return False

        except requests.exceptions.Timeout:
            self.print_error("获取积分请求超时")
            return False
        except requests.exceptions.ConnectionError:
            self.print_error("网络连接错误，请检查网络连接")
            return False
        except json.JSONDecodeError:
            self.print_error("服务器响应格式错误")
            return False
        except Exception as e:
            self.print_error(f"获取积分时发生未知异常: {str(e)}")
            return False

    def check_model_status(self):
        """
        检查模型状态

        Returns:
            bool: 检查是否成功
        """
        try:
            url = f"{self.base_url}/client/common/getModelStatus?model=sora-2"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    self.model_status = data["data"]["status"]
                    if not self.model_status:
                        error_msg = data["data"].get("error", "模型异常")
                        self.print_warning(f"模型状态异常: {error_msg}")
                    return True
                else:
                    error_msg = data.get('msg', '未知错误')
                    self.print_error(f"获取模型状态失败: {error_msg}")
                    return False
            else:
                self.print_error(f"HTTP错误: {response.status_code}")
                return False

        except requests.exceptions.Timeout:
            self.print_error("检查模型状态请求超时")
            return False
        except requests.exceptions.ConnectionError:
            self.print_error("网络连接错误，请检查网络连接")
            return False
        except json.JSONDecodeError:
            self.print_error("服务器响应格式错误")
            return False
        except Exception as e:
            self.print_error(f"检查模型状态时发生未知异常: {str(e)}")
            return False

    @staticmethod
    def download_video(video_url, filename, download_dir):
        """
        下载视频文件

        Args:
            video_url: 视频URL
            filename: 保存的文件名
            download_dir: 下载目录

        Returns:
            tuple: (是否成功, 文件路径或错误信息)
        """
        try:
            # 验证URL格式
            if not VideoGeneratorApp.validate_url(video_url):
                return False, "视频URL格式无效"

            response = requests.get(video_url, stream=True, timeout=60)

            if response.status_code == 200:
                filepath = download_dir / filename

                # 获取文件大小（如果服务器提供）
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0

                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)

                # 验证文件是否下载完整
                if total_size > 0 and downloaded_size < total_size:
                    # 文件不完整，删除
                    try:
                        filepath.unlink()
                    except:
                        pass
                    return False, f"文件下载不完整: {downloaded_size}/{total_size} bytes"

                # 验证文件是否为空
                if filepath.stat().st_size == 0:
                    try:
                        filepath.unlink()
                    except:
                        pass
                    return False, "下载的文件为空"

                return True, str(filepath)
            else:
                return False, f"下载失败: HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            return False, "下载超时"
        except requests.exceptions.ConnectionError:
            return False, "下载连接错误"
        except IOError as e:
            return False, f"文件写入错误: {str(e)}"
        except Exception as e:
            return False, f"下载异常: {str(e)}"

    def rate_limit_api_call(self):
        """控制API调用频率，确保每次调用间隔至少1秒"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call_time

        if time_since_last_call < 1.0:
            time.sleep(1.0 - time_since_last_call)

        self.last_api_call_time = time.time()

    def poll_for_result(self, task_index, api_task_id):
        """
        轮询获取任务结果 - 修改为每15秒轮询一次

        Args:
            task_index: 任务索引
            api_task_id: API任务ID
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {"id": api_task_id}

        max_poll_attempts = 120  # 最多轮询120次（30分钟）
        poll_interval = 15  # 每15秒轮询一次

        for attempt in range(max_poll_attempts):
            # 检查程序是否还在运行
            if not self.is_running:
                return

            # 控制API调用频率
            self.rate_limit_api_call()

            try:
                response = requests.post(
                    f"{self.base_url}/v1/draw/result",
                    headers=headers,
                    json=payload,
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 0:
                        result_data = data["data"]
                        progress = result_data.get("progress", 0)
                        status = result_data.get("status", "")

                        # 使用线程锁更新任务状态
                        with self.lock:
                            if task_index < len(self.tasks) and self.tasks[task_index]:
                                self.tasks[task_index].update({
                                    'progress': progress,
                                    'status': 'generating' if status == 'running' else status,
                                    'last_update': time.time()
                                })

                        if status == "succeeded":
                            results = result_data.get("results", [])
                            if results and len(results) > 0:
                                video_url = results[0].get("url", "")
                                if video_url:
                                    # 下载视频
                                    filename = f"video_{task_index}_{int(time.time())}.mp4"
                                    success, result = self.download_video(video_url, filename, self.download_dir)

                                    with self.lock:
                                        if task_index < len(self.tasks) and self.tasks[task_index]:
                                            if success:
                                                self.tasks[task_index].update({
                                                    'status': 'completed',
                                                    'download_path': str(result),
                                                    'video_url': video_url,
                                                    'end_time': time.time()  # 记录任务结束时间
                                                })
                                                self.print_success(f"任务 {task_index + 1} 视频下载成功: {result}")
                                            else:
                                                self.tasks[task_index].update({
                                                    'status': 'download_failed',
                                                    'error': result,
                                                    'end_time': time.time()  # 记录任务结束时间
                                                })
                                                self.print_error(f"任务 {task_index + 1} 视频下载失败: {result}")
                                    return

                        elif status == "failed":
                            failure_reason = result_data.get("failure_reason", "")
                            error_msg = result_data.get("error", "")
                            with self.lock:
                                if task_index < len(self.tasks) and self.tasks[task_index]:
                                    self.tasks[task_index].update({
                                        'status': 'failed',
                                        'error': f"{failure_reason}: {error_msg}",
                                        'end_time': time.time()  # 记录任务结束时间
                                    })
                            return
                    else:
                        # API返回错误代码
                        with self.lock:
                            if task_index < len(self.tasks) and self.tasks[task_index]:
                                self.tasks[task_index].update({
                                    'error': f"API错误: {data.get('msg', '未知错误')}",
                                    'last_update': time.time()
                                })

                time.sleep(poll_interval)

            except requests.exceptions.Timeout:
                with self.lock:
                    if task_index < len(self.tasks) and self.tasks[task_index]:
                        self.tasks[task_index].update({
                            'error': '轮询请求超时',
                            'last_update': time.time()
                        })
                time.sleep(poll_interval)
            except requests.exceptions.ConnectionError:
                with self.lock:
                    if task_index < len(self.tasks) and self.tasks[task_index]:
                        self.tasks[task_index].update({
                            'error': '轮询连接错误',
                            'last_update': time.time()
                        })
                time.sleep(poll_interval)
            except Exception as e:
                with self.lock:
                    if task_index < len(self.tasks) and self.tasks[task_index]:
                        self.tasks[task_index].update({
                            'error': f'轮询异常: {str(e)}',
                            'last_update': time.time()
                        })
                time.sleep(poll_interval)

        # 轮询超时
        with self.lock:
            if task_index < len(self.tasks) and self.tasks[task_index]:
                self.tasks[task_index].update({
                    'status': 'failed',
                    'error': '轮询超时，请手动检查任务状态',
                    'end_time': time.time()  # 记录任务结束时间
                })

    def generate_video_task(self, task_index, prompt, image_url, aspect_ratio, duration):
        """
        生成视频的单个任务 - 修改为使用轮询方式获取结果

        Args:
            task_index: 任务索引
            prompt: 提示词
            image_url: 图片URL
            aspect_ratio: 视频比例
            duration: 视频时长

        Returns:
            bool: 任务是否成功
        """
        # 检查程序是否还在运行
        if not self.is_running:
            return False

        # 初始化任务状态 - 修复：确保任务在开始前就正确初始化
        with self.lock:
            # 确保task_index在有效范围内
            if task_index >= len(self.tasks):
                return False

            # 如果任务未初始化，则初始化
            if not self.tasks[task_index]:
                self.tasks[task_index] = {
                    'id': task_index,
                    'prompt': prompt,
                    'status': 'pending',
                    'progress': 0,
                    'retry_count': 0,
                    'error': '',
                    'video_url': '',
                    'start_time': time.time(),
                    'last_update': time.time(),
                    'end_time': None  # 添加任务结束时间字段
                }
            else:
                # 如果任务已存在，更新必要字段
                self.tasks[task_index].update({
                    'status': 'pending',
                    'progress': 0,
                    'retry_count': 0,
                    'error': '',
                    'video_url': '',
                    'start_time': time.time(),
                    'last_update': time.time(),
                    'end_time': None  # 重置任务结束时间
                })

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # 构建请求参数 - 设置webHook为"-1"以立即返回任务ID
        payload = {
            "model": "sora-2",
            "prompt": prompt,
            "aspectRatio": aspect_ratio,
            "duration": duration,
            "size": "small",
            "shutProgress": False,
            "webHook": "-1"  # 设置为"-1"以立即返回任务ID，然后使用轮询
        }

        # 添加图片URL（如果提供）
        if image_url and image_url.strip():
            if self.validate_url(image_url.strip()):
                payload["url"] = image_url.strip()
            else:
                with self.lock:
                    if task_index < len(self.tasks) and self.tasks[task_index]:
                        self.tasks[task_index].update({
                            'status': 'failed',
                            'error': '图片URL格式无效',
                            'end_time': time.time()  # 记录任务结束时间
                        })
                return False

        # 重试循环
        for attempt in range(max_retries):
            # 检查程序是否还在运行
            if not self.is_running:
                return False

            try:
                # 更新任务状态为生成中
                with self.lock:
                    if task_index < len(self.tasks) and self.tasks[task_index]:
                        self.tasks[task_index].update({
                            'status': 'generating',
                            'retry_count': attempt,
                            'last_update': time.time()
                        })

                # 控制API调用频率
                self.rate_limit_api_call()

                # 发送生成请求
                response = requests.post(
                    f"{self.base_url}/v1/video/sora-video",
                    headers=headers,
                    json=payload,
                    timeout=120  # 生成请求超时时间设为2分钟
                )

                if response.status_code == 200:
                    data = response.json()

                    # 检查API返回状态
                    if data.get("code") == 0:
                        # 获取任务ID
                        api_task_id = data["data"]["id"]

                        # 开始轮询获取结果
                        self.poll_for_result(task_index, api_task_id)

                        # 检查最终状态
                        final_status = self.tasks[task_index].get('status', 'failed') if task_index < len(
                            self.tasks) and self.tasks[task_index] else 'failed'

                        # 如果任务成功完成，直接返回
                        if final_status == 'completed':
                            return True
                        # 如果任务失败，继续重试循环
                        elif final_status in ['failed', 'download_failed']:
                            # 任务失败，记录错误信息但继续重试
                            self.print_warning(f"任务 {task_index + 1} 第 {attempt + 1} 次尝试失败，准备重试...")
                            continue
                        else:
                            # 未知状态，也继续重试
                            continue

                    else:
                        # API返回错误代码
                        error_msg = data.get('msg', '未知错误')
                        with self.lock:
                            if task_index < len(self.tasks) and self.tasks[task_index]:
                                self.tasks[task_index].update({
                                    'status': 'failed',
                                    'error': f"API错误: {error_msg}",
                                    'last_update': time.time()
                                })
                        # 不设置end_time，因为可能还会重试
                        self.print_warning(f"任务 {task_index + 1} 第 {attempt + 1} 次尝试失败 (API错误)，准备重试...")

                else:
                    # HTTP错误处理
                    error_msg = f"HTTP错误: {response.status_code}"
                    if response.text:
                        try:
                            error_data = response.json()
                            error_msg = error_data.get("msg", error_msg)
                        except:
                            error_msg = response.text[:100]  # 截取前100个字符

                    with self.lock:
                        if task_index < len(self.tasks) and self.tasks[task_index]:
                            self.tasks[task_index].update({
                                'status': 'failed',
                                'error': error_msg,
                                'last_update': time.time()
                            })
                    # 不设置end_time，因为可能还会重试
                    self.print_warning(f"任务 {task_index + 1} 第 {attempt + 1} 次尝试失败 (HTTP错误)，准备重试...")

            except requests.exceptions.Timeout:
                with self.lock:
                    if task_index < len(self.tasks) and self.tasks[task_index]:
                        self.tasks[task_index].update({
                            'status': 'failed',
                            'error': '请求超时',
                            'last_update': time.time()
                        })
                # 不设置end_time，因为可能还会重试
                self.print_warning(f"任务 {task_index + 1} 第 {attempt + 1} 次尝试失败 (请求超时)，准备重试...")
            except requests.exceptions.ConnectionError:
                with self.lock:
                    if task_index < len(self.tasks) and self.tasks[task_index]:
                        self.tasks[task_index].update({
                            'status': 'failed',
                            'error': '连接错误',
                            'last_update': time.time()
                        })
                # 不设置end_time，因为可能还会重试
                self.print_warning(f"任务 {task_index + 1} 第 {attempt + 1} 次尝试失败 (连接错误)，准备重试...")
            except Exception as e:
                with self.lock:
                    if task_index < len(self.tasks) and self.tasks[task_index]:
                        self.tasks[task_index].update({
                            'status': 'failed',
                            'error': f"异常: {str(e)}",
                            'last_update': time.time()
                        })
                # 不设置end_time，因为可能还会重试
                self.print_warning(f"任务 {task_index + 1} 第 {attempt + 1} 次尝试失败 (异常)，准备重试...")

            # 如果不是最后一次尝试，等待后重试（指数退避策略）
            if attempt < max_retries - 1:
                current_status = self.tasks[task_index].get('status', 'failed') if task_index < len(self.tasks) and \
                                                                                   self.tasks[task_index] else 'failed'
                if current_status == 'failed' and self.is_running:
                    wait_time = 2 ** attempt  # 指数退避
                    self.print_info(f"任务 {task_index + 1} 等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)

                    # 重置任务状态以便重试
                    with self.lock:
                        if task_index < len(self.tasks) and self.tasks[task_index]:
                            self.tasks[task_index].update({
                                'status': 'pending',
                                'error': '',
                                'last_update': time.time()
                            })
                    continue
                else:
                    break
            else:
                break

        # 所有重试尝试都已用完，设置最终状态
        final_status = self.tasks[task_index].get('status', 'failed') if task_index < len(self.tasks) and self.tasks[
            task_index] else 'failed'

        # 只有在所有重试都失败后才设置结束时间
        with self.lock:
            if task_index < len(self.tasks) and self.tasks[task_index] and not self.tasks[task_index].get('end_time'):
                self.tasks[task_index]['end_time'] = time.time()

        if final_status == 'completed':
            self.print_success(f"任务 {task_index + 1} 最终成功完成")
        else:
            self.print_error(f"任务 {task_index + 1} 所有 {max_retries} 次重试均失败")

        return final_status == 'completed'

    def display_progress(self):
        """显示进度面板 - 使用ASCII表格美化"""
        # 使用线程锁安全地访问任务数据
        with self.lock:
            tasks_copy = list(self.tasks)  # 创建副本避免竞态条件
            _credits = self.credits

        # 统计任务状态
        completed = sum(1 for task in tasks_copy if task and task.get('status') == 'completed')
        failed = sum(1 for task in tasks_copy if task and task.get('status') in ['failed', 'download_failed'])
        total = len(tasks_copy)
        # 修复：正确计算运行中任务数量
        running = sum(1 for task in tasks_copy if task and task.get('status') in ['generating', 'pending'])

        print("\n" + "╔" + "═" * 78 + "╗")
        print("║" + "📊 视频生成进度面板".center(73) + " ")
        print("╠" + "═" * 78 + "╣")
        print(
            f"║ 总任务: {total:2d} │ 已完成: {completed:2d} │ 失败: {failed:2d} │ 进行中: {running:2d} │ 剩余积分: {_credits:6d}  ")
        print("╠" + "═" * 78 + "╣")

        # 显示每个任务的状态
        for i, task in enumerate(tasks_copy):
            # 修复：正确处理未初始化任务
            if not task:  # 任务未初始化
                print(f"║ 任务 {i + 1:2d}: ❓ 未初始化".ljust(78) + "║")
                continue

            # 状态图标映射
            status_icons = {
                'pending': '⏳',
                'generating': '🔄',
                'completed': '✅',
                'failed': '❌',
                'download_failed': '📥❌'
            }

            icon = status_icons.get(task.get('status', 'pending'), '❓')

            # 计算耗时 - 修复：任务结束后停止计时
            if task.get('end_time'):
                # 任务已结束，使用结束时间计算耗时
                elapsed = int(task['end_time'] - task.get('start_time', time.time()))
            else:
                # 任务仍在进行中，使用当前时间计算耗时
                elapsed = int(time.time() - task.get('start_time', time.time()))

            # 状态文本
            if task.get('status') == 'generating':
                status_text = f"生成中... {task.get('progress', 0):3d}%"
            elif task.get('status') == 'completed':
                status_text = "已完成"
            elif task.get('status') == 'failed':
                error_msg = task.get('error', '未知错误')[:25]  # 截取错误信息
                status_text = f"失败: {error_msg}..."
            elif task.get('status') == 'download_failed':
                error_msg = task.get('error', '未知错误')[:25]
                status_text = f"下载失败: {error_msg}..."
            elif task.get('status') == 'pending':
                status_text = "等待中..."
            else:
                status_text = "未知状态"

            # 重试信息
            retry_count = task.get('retry_count', 0)
            retry_info = f"重试: {retry_count}次" if retry_count > 0 else ""

            print(f"║ 任务 {i + 1:2d}: {icon} {status_text:30} {retry_info:12} 耗时: {elapsed:3d}秒  ")

        print("╠" + "═" * 78 + "╣")
        print("║ 说明: 🔄 生成中 │ ✅ 已完成 │ ❌ 生成失败 │ 📥❌ 下载失败 │ ⏳ 等待中  ")
        print("╚" + "═" * 78 + "╝")

    def get_user_input(self):
        """
        获取用户输入并进行验证

        Returns:
            dict or bool: 成功返回参数字典，失败返回False
        """
        self.clear_screen()
        self.print_header("Sora视频生成器")

        # 从配置文件加载API密钥
        self.print_info("正在从配置文件加载API密钥...")
        if not self.load_config():
            self.print_error("无法从配置文件加载API密钥，程序退出")
            return False

        # 检查积分和模型状态
        self.print_info("正在检查积分余额和模型状态...")
        if not self.get_credits():
            self.print_error("无法获取积分余额，请检查API密钥和网络连接")
            return False

        if not self.check_model_status():
            self.print_warning("无法获取模型状态，但将继续执行")

        self.print_success(f"当前积分: {self.credits}（{int(self.credits / 1600)} 次）")
        self.print_info(f"模型状态: {'正常' if self.model_status else '异常'}")
        print()

        # 视频数量输入 - 修改：最大数量限制为 max_video_count
        while True:
            try:
                count_input = input("【🎥】请输入要生成的视频数量 (1-15，默认1): ").strip()
                if not count_input:
                    video_count = 1
                    break

                video_count = int(count_input)
                if 1 <= video_count <= max_video_count:
                    break
                else:
                    self.print_error(f"请输入1-{max_video_count}之间的数字")
            except ValueError:
                self.print_error("请输入有效的数字")
            except EOFError:
                self.print_error("输入被中断")
                return False
            except KeyboardInterrupt:
                self.print_info("用户取消输入")
                return False

        # 检查积分是否足够
        required_credits = video_count * 1600
        if self.credits < required_credits:
            self.print_error(f"积分不足！需要{required_credits}积分，当前只有{self.credits}积分")
            return False

        # 提示词输入
        while True:
            try:
                prompt = input("【✏️】请输入视频描述提示词 (必填): ").strip()
                if prompt:
                    if len(prompt) < 5:
                        self.print_warning("提示词过短，建议提供更详细的描述")
                    break
                else:
                    self.print_error("提示词不能为空")
            except EOFError:
                self.print_error("输入被中断")
                return False
            except KeyboardInterrupt:
                self.print_info("用户取消输入")
                return False

        # 图片链接输入
        while True:
            try:
                image_url = input("【🖼️】请输入参考图片链接 (选填，直接回车跳过): ").strip()
                if image_url and not self.validate_url(image_url):
                    self.print_error("图片URL格式无效，请重新输入或直接回车跳过")
                    continue
                break
            except EOFError:
                self.print_error("输入被中断")
                return False
            except KeyboardInterrupt:
                self.print_info("用户取消输入")
                return False

        # 横竖屏选择
        while True:
            try:
                aspect_input = input("【📱】请选择视频比例 (0-横屏16:9, 1-竖屏9:16，默认0): ").strip()
                if not aspect_input:
                    aspect_ratio = "16:9"
                    break
                elif aspect_input == "0":
                    aspect_ratio = "16:9"
                    break
                elif aspect_input == "1":
                    aspect_ratio = "9:16"
                    break
                else:
                    self.print_error("请输入0或1")
            except EOFError:
                self.print_error("输入被中断")
                return False
            except KeyboardInterrupt:
                self.print_info("用户取消输入")
                return False

        # 时长选择
        while True:
            try:
                duration_input = input("【⏱️】请选择视频时长 (0-10秒, 1-15秒，默认1): ").strip()
                if not duration_input:
                    duration = 15
                    break
                elif duration_input == "0":
                    duration = 10
                    break
                elif duration_input == "1":
                    duration = 15
                    break
                else:
                    self.print_error("请输入0或1")
            except EOFError:
                self.print_error("输入被中断")
                return False
            except KeyboardInterrupt:
                self.print_info("用户取消输入")
                return False

        # 确认信息
        self.print_header("确认生成参数")
        print(f"【📋】视频数量: {video_count}")
        print(f"【📝】提示词: {prompt}")
        print(f"【🖼️】图片链接: {image_url if image_url else '无'}")
        print(f"【📐】视频比例: {aspect_ratio}")
        print(f"【⏰】视频时长: {duration}秒")
        print(f"【💰】预计消耗积分: {required_credits}")
        print()

        try:
            confirm = input("【🚀】确认开始生成？(y/N): ").strip().lower()
            if confirm not in ['y', 'yes']:
                self.print_info("已取消生成")
                return False
        except (EOFError, KeyboardInterrupt):
            self.print_info("已取消生成")
            return False

        return {
            'video_count': video_count,
            'prompt': prompt,
            'image_url': image_url,
            'aspect_ratio': aspect_ratio,
            'duration': duration
        }

    def run_generation(self, params):
        """
        运行视频生成

        Args:
            params: 生成参数字典
        """
        # 初始化任务列表 - 修复：正确初始化所有任务
        self.tasks = [{
            'id': i,
            'prompt': params['prompt'],
            'status': 'pending',  # pending, generating, completed, failed, download_failed
            'progress': 0,
            'retry_count': 0,
            'error': '',
            'video_url': '',
            'start_time': time.time(),
            'last_update': time.time(),
            'end_time': None  # 添加任务结束时间字段
        } for i in range(params['video_count'])]

        self.print_info("开始视频生成任务...")
        # 修改：最大线程数限制为5或任务数，取较小值
        _max_workers = min(max_workers, params['video_count'])
        self.print_info(f"使用线程数: {_max_workers}")

        # 使用线程池执行任务
        start_time = time.time()
        try:
            with ThreadPoolExecutor(max_workers=_max_workers) as executor:
                # 提交所有任务
                future_to_task = {}
                for i in range(params['video_count']):
                    future = executor.submit(
                        self.generate_video_task,
                        i,
                        params['prompt'],
                        params['image_url'],
                        params['aspect_ratio'],
                        params['duration']
                    )
                    future_to_task[future] = i

                # 定期更新进度显示
                last_refresh = 0
                while True:
                    current_time = time.time()

                    # 每15秒刷新一次完整界面
                    if current_time - last_refresh >= 15:
                        self.clear_screen()
                        self.display_progress()
                        last_refresh = current_time

                    # 检查是否所有任务都完成
                    with self.lock:
                        completed_count = sum(1 for task in self.tasks
                                              if
                                              task and task.get('status') in ['completed', 'failed', 'download_failed'])

                    if completed_count == len(self.tasks):
                        break

                    time.sleep(1)  # 每秒检查一次
        except Exception as e:
            self.print_error(f"任务执行异常: {str(e)}")

        # 最终结果显示
        self.clear_screen()
        self.display_progress()

        # 统计结果
        with self.lock:
            success_count = sum(1 for task in self.tasks if task and task.get('status') == 'completed')
            failed_count = len(self.tasks) - success_count

        total_time = int(time.time() - start_time)

        print("\n" + "╔" + "═" * 60 + "╗")
        print("║" + "📋 生成结果汇总".center(54) + " ")
        print("╠" + "═" * 60 + "╣")
        print(f"║ 【✓】成功: {success_count:2d}个".ljust(58) + " ")
        print(f"║ 【✗】失败: {failed_count:2d}个".ljust(58) + " ")
        print(f"║ 【⏰】总耗时: {total_time:3d}秒".ljust(58) + " ")

        if success_count > 0:
            download_path = self.download_dir.absolute()
            print(f"║ 【📁】视频保存到: {download_path}".ljust(58) + " ")

        print("╚" + "═" * 60 + "╝")

        # 显示失败任务的错误信息
        if failed_count > 0:
            print("\n【!】失败任务详情:")
            with self.lock:
                for i, task in enumerate(self.tasks):
                    if task and task.get('status') in ['failed', 'download_failed']:
                        print(f"   任务 {i + 1}: {task.get('error', '未知错误')}")

        # try:
        #     input("\n【↵】按下回车键退出...")
        # except (EOFError, KeyboardInterrupt):
        #     pass

    def run(self):
        """运行主程序"""
        try:
            self.print_info("启动Sora视频生成器...")
            params = self.get_user_input()
            if params:
                self.run_generation(params)
            else:
                self.print_info("程序结束")
        except KeyboardInterrupt:
            self.print_info("\n程序被用户中断")
        except Exception as e:
            self.print_error(f"程序运行异常: {str(e)}")
        finally:
            # 设置运行标志为False，通知所有线程停止
            self.is_running = False
            try:
                input("\n【↵】按下回车键退出...")
            except (EOFError, KeyboardInterrupt):
                pass

    @staticmethod
    def create_sample_config():
        """创建示例配置文件"""
        config_path = Path("config.json")
        if not config_path.exists():
            sample_config = {
                "api_key": "sk-your-api-key-here"
            }
            with open(config_path, 'w') as f:  # 创建配置文件
                data = json.dumps(sample_config, indent=4, ensure_ascii=False)
                f.write(data)
            print("已创建示例配置文件 config.json")
            print("请编辑该文件并填入您的API密钥")
        else:
            print("配置文件 config.json 已存在")


def main():
    """主函数"""
    try:
        # 检查是否需要创建示例配置文件
        if len(sys.argv) > 1 and sys.argv[1] == "--create-config":
            VideoGeneratorApp().create_sample_config()
            return

        app = VideoGeneratorApp()
        app.run()
    except KeyboardInterrupt:
        print("\n【!】程序被用户中断")
    except Exception as e:
        print(f"【✗】程序启动失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()