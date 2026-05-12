"""
版本检查模块 - 检测新版本并提醒用户更新
"""
import json
import urllib.request
from pathlib import Path
from typing import Optional, Dict, Tuple


class VersionChecker:
    """版本检查器"""
    
    # GitHub 配置
    GITHUB_OWNER = "carterwang1713"
    GITHUB_REPO = "bill-cleaner-config"
    VERSION_FILE = "version.json"
    
    # 当前版本（每次发版时更新）
    CURRENT_VERSION = "1.0.0"
    
    def __init__(self, local_version_file: Optional[Path] = None):
        """
        初始化版本检查器
        
        Args:
            local_version_file: 本地版本文件路径
        """
        self.local_version_file = local_version_file
    
    def _get_version_url(self) -> str:
        """获取版本文件URL"""
        return f"https://raw.githubusercontent.com/{self.GITHUB_OWNER}/{self.GITHUB_REPO}/main/{self.VERSION_FILE}"
    
    def fetch_remote_version(self) -> Optional[Dict]:
        """
        获取远程版本信息
        
        Returns:
            版本信息字典，失败返回 None
        """
        try:
            url = self._get_version_url()
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'BillCleaner/1.0')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"[版本检查] 获取远程版本失败: {e}")
            return None
    
    def get_local_version(self) -> str:
        """获取本地版本"""
        if self.local_version_file and self.local_version_file.exists():
            try:
                with open(self.local_version_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('version', self.CURRENT_VERSION)
            except:
                pass
        return self.CURRENT_VERSION
    
    def compare_versions(self, v1: str, v2: str) -> int:
        """
        比较两个版本号
        
        Args:
            v1: 版本1
            v2: 版本2
        
        Returns:
            -1: v1 < v2
             0: v1 == v2
             1: v1 > v2
        """
        try:
            parts1 = [int(x) for x in v1.split('.')]
            parts2 = [int(x) for x in v2.split('.')]
            
            # 补齐版本号长度
            max_len = max(len(parts1), len(parts2))
            parts1.extend([0] * (max_len - len(parts1)))
            parts2.extend([0] * (max_len - len(parts2)))
            
            for p1, p2 in zip(parts1, parts2):
                if p1 < p2:
                    return -1
                elif p1 > p2:
                    return 1
            return 0
        except:
            return 0
    
    def check_update(self) -> Tuple[bool, Optional[Dict]]:
        """
        检查是否有更新
        
        Returns:
            (是否有更新, 版本信息)
        """
        remote_info = self.fetch_remote_version()
        if not remote_info:
            return False, None
        
        remote_version = remote_info.get('version', '0.0.0')
        local_version = self.get_local_version()
        
        has_update = self.compare_versions(local_version, remote_version) < 0
        
        return has_update, remote_info
    
    def show_update_notification(self, version_info: Dict) -> bool:
        """
        显示更新通知
        
        Args:
            version_info: 版本信息
        
        Returns:
            用户是否选择更新
        """
        print("\n" + "=" * 50)
        print("  📢 发现新版本！")
        print("=" * 50)
        print()
        print(f"  当前版本: {self.get_local_version()}")
        print(f"  最新版本: {version_info.get('version', 'N/A')}")
        print(f"  发布日期: {version_info.get('release_date', 'N/A')}")
        print()
        
        # 显示更新日志
        changelog = version_info.get('changelog', [])
        if changelog:
            print("  更新内容:")
            for item in changelog:
                print(f"    • {item}")
            print()
        
        # 是否强制更新
        force_update = version_info.get('force_update', False)
        download_url = version_info.get('download_url', '')
        
        if force_update:
            print("  ⚠️ 此版本为强制更新，请立即更新！")
            print(f"  下载地址: {download_url}")
            print()
            return True
        else:
            print(f"  下载地址: {download_url}")
            print()
            choice = input("  是否现在去下载? (y/n): ").strip().lower()
            return choice == 'y'


def check_version_on_startup() -> bool:
    """
    启动时检查版本更新（简化接口）
    
    Returns:
        是否有更新
    """
    checker = VersionChecker()
    has_update, version_info = checker.check_update()
    
    if has_update and version_info:
        checker.show_update_notification(version_info)
        return True
    
    return False


if __name__ == "__main__":
    # 测试
    checker = VersionChecker()
    has_update, info = checker.check_update()
    
    if has_update:
        print(f"有新版本: {info.get('version')}")
    else:
        print("已是最新版本")
