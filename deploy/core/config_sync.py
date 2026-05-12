"""
配置同步模块 - 从 GitHub 自动拉取最新配置
优化：批量下载 + 重试机制，避免 GitHub 限流导致 WinError 10054
"""
import json
import urllib.request
import urllib.parse
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from loguru import logger


class ConfigSync:
    """配置同步管理器"""
    
    # GitHub 配置
    GITHUB_OWNER = "carterwang1713"
    GITHUB_REPO = "bill-cleaner-config"
    GITHUB_BRANCH = "main"
    
    # 配置文件列表（需要同步的文件）
    CONFIG_FILES = [
        "mappings_config/column_name_full_mapping.json",
        "mappings_config/column_name_full_mapping.csv",
        "mappings_config/column_name_mapping.json",
        "mappings_config/column_name_mapping.csv",
        "mappings_config/matching_helper_to_chinese.json",
        "mappings_config/matching_helper_to_chinese.csv",
        "mappings_config/two_dimension_mapping.json",
        "mappings_config/two_dimension_mapping.csv",
        "mappings_config/performance_dimension_mapping.csv",
        "mappings_config/汇率表_各币种兑美元.csv",
        "mappings_config/规则表1_无需关注description的type列表.csv",
        "mappings_config/规则表2_需关注部分description的type规则.csv",
        "mappings_config/规则表3_需关注全部description的type示例.csv",
        "mappings_config/完整映射表.csv",
        "mappings_config/序列码绩效维度映射.json",
        "mappings_config/accounts.json",  # 用户账号也云端同步
    ]
    
    # 批量下载配置
    MAX_RETRIES = 3          # 单文件最大重试次数
    RETRY_DELAY = 2          # 重试间隔（秒）
    REQUEST_INTERVAL = 0.3   # 请求间隔（秒），避免触发限流
    
    def __init__(self, local_config_dir: Path):
        """
        初始化配置同步器
        
        Args:
            local_config_dir: 本地配置目录路径
        """
        self.local_config_dir = local_config_dir
        self.version_file = local_config_dir / ".version"
    
    def _get_github_api_url(self, file_path: str) -> str:
        """获取 GitHub API 地址"""
        encoded_path = urllib.parse.quote(file_path, safe='/')
        return f"https://api.github.com/repos/{self.GITHUB_OWNER}/{self.GITHUB_REPO}/contents/{encoded_path}?ref={self.GITHUB_BRANCH}"
    
    def _get_raw_url(self, file_path: str) -> str:
        """获取 GitHub Raw 文件地址"""
        encoded_path = urllib.parse.quote(file_path, safe='/')
        return f"https://raw.githubusercontent.com/{self.GITHUB_OWNER}/{self.GITHUB_REPO}/{self.GITHUB_BRANCH}/{encoded_path}"
    
    def _request_with_retry(self, url: str, timeout: int = 30) -> Optional[bytes]:
        """
        带重试的 HTTP 请求
        
        Args:
            url: 请求地址
            timeout: 超时时间（秒）
        
        Returns:
            响应内容（字节），失败返回 None
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                req = urllib.request.Request(url)
                req.add_header('User-Agent', 'BillCleaner/1.0')
                
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    return response.read()
            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    wait = self.RETRY_DELAY * (attempt + 1)  # 递增等待
                    print(f"    ⚠️ 请求失败({attempt + 1}/{self.MAX_RETRIES})，{wait}秒后重试: {e}")
                    time.sleep(wait)
                else:
                    print(f"    ✗ 请求失败，已重试{self.MAX_RETRIES}次: {e}")
                    return None
        return None
    
    def _get_directory_listing(self, dir_path: str = "mappings_config") -> Dict[str, str]:
        """
        批量获取目录下所有文件的下载地址（一次API调用）
        
        Args:
            dir_path: GitHub 上的目录路径
        
        Returns:
            文件路径 -> raw URL 的映射字典
        """
        url_map = {}
        
        try:
            # 递归获取目录树（一次API调用拿全部文件）
            api_url = f"https://api.github.com/repos/{self.GITHUB_OWNER}/{self.GITHUB_REPO}/git/trees/{self.GITHUB_BRANCH}?recursive=1"
            req = urllib.request.Request(api_url)
            req.add_header('User-Agent', 'BillCleaner/1.0')
            
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            if data.get('truncated'):
                print("    ⚠️ 目录树被截断，文件较多，将逐个下载")
            
            for item in data.get('tree', []):
                if item['type'] == 'blob' and item['path'].startswith(dir_path + '/'):
                    # 构建raw URL
                    raw_url = self._get_raw_url(item['path'])
                    url_map[item['path']] = raw_url
            
            print(f"    ✓ 获取目录列表成功，共 {len(url_map)} 个文件")
            
        except Exception as e:
            print(f"    ⚠️ 获取目录列表失败，回退逐个下载模式: {e}")
        
        return url_map
    
    def fetch_file_from_github(self, file_path: str, url_map: Dict[str, str] = None) -> Optional[bytes]:
        """
        从 GitHub 获取文件内容（支持批量URL映射）
        
        Args:
            file_path: GitHub 上的文件路径
            url_map: 目录列表映射（可选，有的话直接用raw URL下载）
        
        Returns:
            文件内容（字节），失败返回 None
        """
        # 优先使用目录列表中的URL
        if url_map and file_path in url_map:
            url = url_map[file_path]
        else:
            url = self._get_raw_url(file_path)
        
        return self._request_with_retry(url)
    
    def get_remote_version(self) -> Optional[str]:
        """
        获取远程配置版本（使用 commit hash）
        
        Returns:
            版本字符串，失败返回 None
        """
        try:
            url = f"https://api.github.com/repos/{self.GITHUB_OWNER}/{self.GITHUB_REPO}/commits?path=mappings_config&per_page=1"
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'BillCleaner/1.0')
            
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
                if data:
                    return data[0].get('sha', '')[:8]
        except:
            pass
        return None
    
    def get_local_version(self) -> Optional[str]:
        """获取本地配置版本"""
        if self.version_file.exists():
            try:
                with open(self.version_file, 'r') as f:
                    data = json.load(f)
                    return data.get('version')
            except:
                pass
        return None
    
    def save_local_version(self, version: str):
        """保存本地配置版本"""
        try:
            with open(self.version_file, 'w') as f:
                json.dump({
                    'version': version,
                    'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }, f)
        except:
            pass
    
    def sync_configs(self, force: bool = False) -> Dict:
        """
        同步配置文件（批量模式）
        
        优化流程：
        1. 一次API调用获取目录树（所有文件的下载地址）
        2. 逐个下载文件，请求间加间隔避免限流
        3. 单文件失败自动重试（最多3次，递增等待）
        4. 失败的文件使用本地缓存
        
        Args:
            force: 是否强制同步（忽略版本检查）
        
        Returns:
            同步结果字典
        """
        result = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'files': []
        }
        
        print("\n[配置同步] 检查远程配置...")
        
        # 检查版本
        remote_version = self.get_remote_version()
        local_version = self.get_local_version()
        
        if not force and remote_version and local_version:
            if remote_version == local_version:
                print(f"    ✓ 配置已是最新版本: {remote_version}")
                result['skipped'] = len(self.CONFIG_FILES) - 1  # accounts.json 仍然同步
                
                # 账号文件每次都同步，不受版本检查影响
                accounts_file = "mappings_config/accounts.json"
                accounts_path = self.local_config_dir / accounts_file
                
                # 获取目录列表用于下载
                url_map = self._get_directory_listing()
                accounts_content = self.fetch_file_from_github(accounts_file, url_map)
                if accounts_content:
                    accounts_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(accounts_path, 'wb') as f:
                        f.write(accounts_content)
                    print(f"    ✓ 账号文件已同步")
                
                return result
        
        if remote_version:
            print(f"    远程版本: {remote_version}")
        if local_version:
            print(f"    本地版本: {local_version}")
        
        print("\n[配置同步] 批量获取文件列表...")
        # 批量获取目录树（核心优化：一次API调用替代N次）
        url_map = self._get_directory_listing()
        
        print(f"\n[配置同步] 开始下载配置文件（共 {len(self.CONFIG_FILES)} 个）...")
        
        for i, config_file in enumerate(self.CONFIG_FILES):
            # 确保目录存在
            local_path = self.local_config_dir / config_file
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 从 GitHub 下载
            content = self.fetch_file_from_github(config_file, url_map)
            
            if content:
                try:
                    with open(local_path, 'wb') as f:
                        f.write(content)
                    print(f"    ✓ {Path(config_file).name}")
                    result['success'] += 1
                    result['files'].append(config_file)
                except Exception as e:
                    print(f"    ✗ {Path(config_file).name}: 保存失败")
                    result['failed'] += 1
            else:
                # 使用本地缓存
                if local_path.exists():
                    print(f"    ⚠️ {Path(config_file).name}: 使用本地缓存")
                    result['skipped'] += 1
                else:
                    result['failed'] += 1
            
            # 请求间加间隔，避免触发GitHub限流
            if i < len(self.CONFIG_FILES) - 1:
                time.sleep(self.REQUEST_INTERVAL)
        
        # 保存版本信息
        if remote_version and result['success'] > 0:
            self.save_local_version(remote_version)
            print(f"\n[配置同步] 完成！成功: {result['success']}, 失败: {result['failed']}, 跳过: {result['skipped']}")
        
        return result
    
    def check_update(self) -> bool:
        """
        检查是否有配置更新
        
        Returns:
            是否有更新
        """
        remote_version = self.get_remote_version()
        local_version = self.get_local_version()
        
        if remote_version and local_version:
            return remote_version != local_version
        
        return remote_version is not None


def sync_configs_on_startup(config_dir: Path, silent: bool = False) -> bool:
    """
    启动时同步配置（简化接口）
    
    优化：如果本地配置在24小时内更新过，跳过同步，减少GitHub请求压力
    
    Args:
        config_dir: 配置目录
        silent: 是否静默模式（不显示输出）
    
    Returns:
        是否同步成功
    """
    sync = ConfigSync(config_dir)
    
    # 先检查远程版本，如果远程版本和本地版本一致则跳过
    try:
        remote_version = sync.get_remote_version()
        local_version = sync.get_local_version()
        
        if remote_version and local_version and remote_version == local_version:
            logger.info(f"配置已是最新版本: {local_version}")
            # 仍然同步账号文件
            return True
        elif remote_version and local_version:
            logger.info(f"配置版本不一致 - 本地: {local_version}, 远程: {remote_version}, 开始同步")
        elif remote_version and not local_version:
            logger.info(f"本地无版本记录, 远程版本: {remote_version}, 开始同步")
    except Exception as e:
        logger.warning(f"版本检查失败: {e}")
    
    try:
        result = sync.sync_configs()
        # 更新本地版本号和同步时间
        if result['success'] > 0 or result['skipped'] > 0:
            # 重新获取远程版本号并保存到本地
            new_version = sync.get_remote_version()
            if new_version:
                sync.save_local_version(new_version)
            logger.info(f"同步完成，成功: {result['success']}, 失败: {result['failed']}, 跳过: {result['skipped']}")
        return result['success'] > 0 or result['skipped'] > 0
    except Exception as e:
        logger.error(f"配置同步失败: {e}")
        return False


if __name__ == "__main__":
    # 测试
    import sys
    if len(sys.argv) > 1:
        config_dir = Path(sys.argv[1])
    else:
        config_dir = Path(__file__).parent.parent / "mappings_config"
    
    print(f"配置目录: {config_dir}")
    sync = ConfigSync(config_dir)
    sync.sync_configs()
