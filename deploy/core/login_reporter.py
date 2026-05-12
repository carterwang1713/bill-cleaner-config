"""
登录记录上报模块
向GitHub提交登录记录，用于监控账号使用情况
"""
import json
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional, Dict
import platform
import socket
import logging

logger = logging.getLogger(__name__)

# GitHub配置
GITHUB_OWNER = "carterwang1713"
GITHUB_REPO = "bill-cleaner-config"
GITHUB_TOKEN = "GITHUB_TOKEN_PLACEHOLDER"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"


def get_device_info() -> Dict:
    """获取设备信息"""
    try:
        hostname = socket.gethostname()
    except:
        hostname = "Unknown"
    
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "hostname": hostname,
        "python_version": platform.python_version()
    }


def get_public_ip() -> str:
    """获取公网IP地址"""
    ip_services = [
        "https://api.ipify.org?format=text",
        "https://icanhazip.com",
        "https://ifconfig.me/ip"
    ]
    
    for service in ip_services:
        try:
            req = urllib.request.Request(service)
            req.add_header('User-Agent', 'Mozilla/5.0')
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.read().decode('utf-8').strip()
        except:
            continue
    
    return "Unknown"


def upload_login_log(phone: str, login_time: str, ip: str, device_info: Dict) -> bool:
    """
    上传登录记录到GitHub
    
    Args:
        phone: 手机号
        login_time: 登录时间
        ip: IP地址
        device_info: 设备信息
    
    Returns:
        是否上传成功
    """
    try:
        # 登录记录文件路径
        file_path = f"login_logs/{phone}.json"
        
        # 获取现有日志
        existing_logs = []
        sha = None
        
        try:
            url = f"{GITHUB_API_URL}/contents/{file_path}"
            req = urllib.request.Request(url)
            req.add_header('Authorization', f'token {GITHUB_TOKEN}')
            req.add_header('User-Agent', 'BillCleaner/1.0')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                sha = data.get('sha')
                content = data.get('content', '')
                # Base64解码
                import base64
                existing_logs = json.loads(base64.b64decode(content).decode('utf-8'))
        except:
            # 文件不存在，创建新文件
            pass
        
        # 添加新记录
        new_log = {
            "phone": phone,
            "login_time": login_time,
            "ip": ip,
            "device": device_info
        }
        existing_logs.append(new_log)
        
        # 只保留最近100条记录
        if len(existing_logs) > 100:
            existing_logs = existing_logs[-100:]
        
        # 上传到GitHub
        import base64
        content = json.dumps(existing_logs, ensure_ascii=False, indent=2)
        encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        commit_data = {
            "message": f"登录记录: {phone} @ {login_time}",
            "content": encoded_content
        }
        
        if sha:
            commit_data["sha"] = sha
        
        url = f"{GITHUB_API_URL}/contents/{file_path}"
        req = urllib.request.Request(url, method='PUT')
        req.add_header('Authorization', f'token {GITHUB_TOKEN}')
        req.add_header('User-Agent', 'BillCleaner/1.0')
        req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(req, json.dumps(commit_data).encode('utf-8'), timeout=15) as response:
            result = json.loads(response.read().decode('utf-8'))
            logger.info(f"登录记录已上传: {phone}")
            return True
    
    except Exception as e:
        logger.warning(f"上传登录记录失败: {e}")
        return False


def report_login(phone: str) -> bool:
    """
    上报登录信息（主入口）
    
    Args:
        phone: 手机号
    
    Returns:
        是否上报成功
    """
    try:
        login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ip = get_public_ip()
        device_info = get_device_info()
        
        logger.info(f"登录上报: {phone}, IP: {ip}, 设备: {device_info.get('hostname', 'Unknown')}")
        
        return upload_login_log(phone, login_time, ip, device_info)
    
    except Exception as e:
        logger.warning(f"登录上报失败: {e}")
        return False


def fetch_login_logs(phone: str) -> list:
    """
    获取指定账号的登录记录
    
    Args:
        phone: 手机号
    
    Returns:
        登录记录列表
    """
    try:
        file_path = f"login_logs/{phone}.json"
        url = f"{GITHUB_API_URL}/contents/{file_path}"
        req = urllib.request.Request(url)
        req.add_header('Authorization', f'token {GITHUB_TOKEN}')
        req.add_header('User-Agent', 'BillCleaner/1.0')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            import base64
            content = base64.b64decode(data.get('content', '')).decode('utf-8')
            return json.loads(content)
    
    except:
        return []
