"""
认证模块 - 账号密码管理
支持时间有效期验证
支持云端同步到GitHub
"""
import hashlib
import json
import base64
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List


def hash_password(password: str) -> str:
    """
    使用SHA256加密密码
    
    Args:
        password: 明文密码
    
    Returns:
        加密后的密码哈希
    """
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def get_accounts_file() -> Path:
    """获取账号文件路径"""
    if hasattr(__builtins__, '__dict__'):
        if '__file__' in dir():
            return Path(__file__).parent.parent / "mappings_config" / "accounts.json"
    return Path("mappings_config/accounts.json")


# GitHub 配置
GITHUB_OWNER = "carterwang1713"
GITHUB_REPO = "bill-cleaner-config"
GITHUB_BRANCH = "main"
GITHUB_TOKEN = "GITHUB_TOKEN_PLACEHOLDER"


def sync_accounts_to_github() -> bool:
    """
    将本地 accounts.json 同步到 GitHub
    
    Returns:
        是否成功
    """
    try:
        accounts_file = get_accounts_file()
        if not accounts_file.exists():
            print("accounts.json 不存在，无法同步")
            return False
        
        # 读取本地文件
        with open(accounts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 获取 GitHub 上的文件 SHA（用于更新）
        api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/mappings_config/accounts.json"
        
        req = urllib.request.Request(api_url)
        req.add_header('Authorization', f'token {GITHUB_TOKEN}')
        req.add_header('Accept', 'application/vnd.github.v3+json')
        req.add_header('User-Agent', 'BillCleaner/1.0')
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                sha = result.get('sha', '')
        except:
            sha = ''  # 文件不存在，新建
        
        # 准备更新请求
        update_data = {
            "message": f"Update accounts.json - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "content": base64.b64encode(content.encode('utf-8')).decode('utf-8'),
            "branch": GITHUB_BRANCH
        }
        if sha:
            update_data["sha"] = sha
        
        # 推送到 GitHub
        req = urllib.request.Request(api_url, data=json.dumps(update_data).encode('utf-8'), method='PUT')
        req.add_header('Authorization', f'token {GITHUB_TOKEN}')
        req.add_header('Accept', 'application/vnd.github.v3+json')
        req.add_header('User-Agent', 'BillCleaner/1.0')
        req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f"✅ accounts.json 已同步到 GitHub")
            return True
            
    except Exception as e:
        print(f"❌ 同步到 GitHub 失败: {e}")
        return False


class AuthManager:
    """认证管理器"""
    
    DEFAULT_ADMIN_PASSWORD = "admin123"
    
    def __init__(self, accounts_file: Optional[Path] = None):
        """
        初始化认证管理器
        
        Args:
            accounts_file: 账号文件路径
        """
        self.accounts_file = accounts_file or get_accounts_file()
        self._ensure_accounts_file()
    
    def _ensure_accounts_file(self):
        """确保账号文件存在"""
        if not self.accounts_file.exists():
            self.accounts_file.parent.mkdir(parents=True, exist_ok=True)
            default_admin_hash = hash_password(self.DEFAULT_ADMIN_PASSWORD)
            initial_data = {
                "admin_password": default_admin_hash,
                "users": [],
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(self.accounts_file, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, ensure_ascii=False, indent=2)
    
    def load_accounts(self) -> Dict:
        """加载账号数据"""
        try:
            with open(self.accounts_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"admin_password": "", "users": []}
    
    def save_accounts(self, accounts: Dict) -> bool:
        """保存账号数据"""
        try:
            with open(self.accounts_file, 'w', encoding='utf-8') as f:
                json.dump(accounts, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存账号失败: {e}")
            return False
    
    def verify_admin_password(self, password: str) -> bool:
        """验证管理员密码"""
        accounts = self.load_accounts()
        stored_hash = accounts.get("admin_password", "")
        input_hash = hash_password(password)
        return stored_hash == input_hash
    
    def change_admin_password(self, old_password: str, new_password: str) -> tuple:
        """修改管理员密码"""
        if not self.verify_admin_password(old_password):
            return False, "旧密码错误"
        if len(new_password) < 6:
            return False, "新密码长度不能少于6位"
        accounts = self.load_accounts()
        accounts["admin_password"] = hash_password(new_password)
        if self.save_accounts(accounts):
            return True, "管理员密码修改成功"
        return False, "保存失败"
    
    def register_account(self, phone: str, password: str, 
                         start_time: str = None, end_time: str = None) -> tuple:
        """
        注册新账号
        
        Args:
            phone: 手机号
            password: 密码
            start_time: 启用时间 (YYYY-MM-DD)
            end_time: 到期时间 (YYYY-MM-DD)
        """
        accounts = self.load_accounts()
        
        # 检查手机号是否已存在
        for user in accounts.get("users", []):
            if user.get("phone") == phone:
                return False, f"手机号 '{phone}' 已存在"
        
        # 验证密码长度
        if len(password) < 6:
            return False, "密码长度不能少于6位"
        
        # 默认时间：当天启用，有效期1年
        if not start_time:
            start_time = datetime.now().strftime("%Y-%m-%d")
        if not end_time:
            end_time = datetime(datetime.now().year + 1, datetime.now().month, datetime.now().day).strftime("%Y-%m-%d")
        
        # 创建新用户
        new_user = {
            "phone": phone,
            "password_hash": hash_password(password),
            "start_time": start_time,
            "end_time": end_time,
            "created_at": datetime.now().strftime("%Y-%m-%d"),
            "last_login": None,
            "status": "active"
        }
        
        accounts.setdefault("users", []).append(new_user)
        
        if self.save_accounts(accounts):
            # 同步到 GitHub（异步，不阻塞）
            import threading
            threading.Thread(target=sync_accounts_to_github, daemon=True).start()
            return True, f"账号 '{phone}' 注册成功！有效期: {start_time} 至 {end_time}"
        return False, "注册失败，请重试"
    
    def login(self, phone: str, password: str) -> tuple:
        """
        用户登录验证（含时间检查）
        
        Args:
            phone: 手机号
            password: 密码
        
        Returns:
            (是否成功, 消息, 剩余天数或None)
        """
        accounts = self.load_accounts()
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")
        
        # 查找用户
        for user in accounts.get("users", []):
            if user.get("phone") == phone:
                # 验证密码
                input_hash = hash_password(password)
                if user.get("password_hash") != input_hash:
                    return False, "密码错误", None
                
                # 检查时间有效期
                start_time = user.get("start_time", "")
                end_time = user.get("end_time", "")
                
                # 未设置时间，默认有效
                if not start_time or not end_time:
                    user["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.save_accounts(accounts)
                    return True, f"欢迎回来，{phone}！", None
                
                # 检查是否在有效期内
                if start_time <= today_str <= end_time:
                    user["last_login"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.save_accounts(accounts)
                    
                    # 上报登录记录到GitHub
                    try:
                        from core.login_reporter import report_login
                        import threading
                        # 异步上报，不阻塞登录流程
                        threading.Thread(target=report_login, args=(phone,), daemon=True).start()
                    except Exception as e:
                        print(f"登录上报失败: {e}")
                    
                    # 计算剩余天数
                    end_date = datetime.strptime(end_time, "%Y-%m-%d")
                    remaining_days = (end_date - today).days
                    
                    return True, f"欢迎回来，{phone}！", remaining_days
                elif today_str < start_time:
                    return False, f"账号未到启用时间，启用日期: {start_time}", None
                else:
                    return False, "已过期，请续费", 0
        
        return False, f"手机号 '{phone}' 不存在", None
    
    def list_users(self) -> List[Dict]:
        """获取所有用户列表"""
        accounts = self.load_accounts()
        return accounts.get("users", [])
    
    def update_user_time(self, phone: str, start_time: str, end_time: str, 
                         admin_password: str) -> tuple:
        """
        更新用户有效期
        
        Args:
            phone: 手机号
            start_time: 启用时间
            end_time: 到期时间
            admin_password: 管理员密码
        """
        if not self.verify_admin_password(admin_password):
            return False, "管理员密码错误"
        
        accounts = self.load_accounts()
        users = accounts.get("users", [])
        
        for user in users:
            if user.get("phone") == phone:
                user["start_time"] = start_time
                user["end_time"] = end_time
                if self.save_accounts(accounts):
                    import threading
                    threading.Thread(target=sync_accounts_to_github, daemon=True).start()
                    return True, f"已更新 {phone} 的有效期: {start_time} 至 {end_time}"
                return False, "保存失败"
        
        return False, f"手机号 '{phone}' 不存在"
    
    def delete_user(self, phone: str, admin_password: str) -> tuple:
        """删除用户"""
        if not self.verify_admin_password(admin_password):
            return False, "管理员密码错误"
        
        accounts = self.load_accounts()
        users = accounts.get("users", [])
        
        for i, user in enumerate(users):
            if user.get("phone") == phone:
                users.pop(i)
                accounts["users"] = users
                if self.save_accounts(accounts):
                    import threading
                    threading.Thread(target=sync_accounts_to_github, daemon=True).start()
                    return True, f"用户 '{phone}' 已删除"
                return False, "删除失败"
        
        return False, f"手机号 '{phone}' 不存在"
    
    def reset_password(self, phone: str, new_password: str, 
                       admin_password: str) -> tuple:
        """重置用户密码"""
        if not self.verify_admin_password(admin_password):
            return False, "管理员密码错误"
        
        if len(new_password) < 6:
            return False, "密码长度不能少于6位"
        
        accounts = self.load_accounts()
        users = accounts.get("users", [])
        
        for user in users:
            if user.get("phone") == phone:
                user["password_hash"] = hash_password(new_password)
                if self.save_accounts(accounts):
                    import threading
                    threading.Thread(target=sync_accounts_to_github, daemon=True).start()
                    return True, f"已重置 {phone} 的密码"
                return False, "保存失败"
        
        return False, f"手机号 '{phone}' 不存在"
    
    def is_first_run(self) -> bool:
        """检查是否为首次运行（无用户账号）"""
        accounts = self.load_accounts()
        return len(accounts.get("users", [])) == 0


# Web后台需要的函数
def get_all_users() -> List[Dict]:
    """获取所有用户（用于Web后台）"""
    auth = AuthManager()
    users = auth.list_users()
    # 隐藏密码哈希
    for user in users:
        user.pop("password_hash", None)
    return users


def add_user_web(phone: str, password: str, start_time: str, end_time: str) -> tuple:
    """Web后台添加用户"""
    auth = AuthManager()
    return auth.register_account(phone, password, start_time, end_time)


def update_user_time_web(phone: str, start_time: str, end_time: str) -> tuple:
    """Web后台更新用户时间（跳过密码验证，使用内部方法）"""
    auth = AuthManager()
    accounts = auth.load_accounts()
    users = accounts.get("users", [])
    
    for user in users:
        if user.get("phone") == phone:
            user["start_time"] = start_time
            user["end_time"] = end_time
            if auth.save_accounts(accounts):
                return True, f"已更新 {phone} 的有效期"
            return False, "保存失败"
    
    return False, f"手机号 '{phone}' 不存在"


def delete_user_web(phone: str) -> tuple:
    """Web后台删除用户"""
    auth = AuthManager()
    accounts = auth.load_accounts()
    users = accounts.get("users", [])
    
    for i, user in enumerate(users):
        if user.get("phone") == phone:
            users.pop(i)
            accounts["users"] = users
            if auth.save_accounts(accounts):
                return True, f"已删除 {phone}"
            return False, "保存失败"
    
    return False, f"手机号 '{phone}' 不存在"


def reset_password_web(phone: str, new_password: str) -> tuple:
    """Web后台重置密码"""
    auth = AuthManager()
    
    if len(new_password) < 6:
        return False, "密码长度不能少于6位"
    
    accounts = auth.load_accounts()
    users = accounts.get("users", [])
    
    for user in users:
        if user.get("phone") == phone:
            user["password_hash"] = hash_password(new_password)
            if auth.save_accounts(accounts):
                return True, f"已重置 {phone} 的密码"
            return False, "保存失败"
    
    return False, f"手机号 '{phone}' 不存在"


def verify_admin(password: str) -> bool:
    """验证管理员密码（Web后台用）"""
    auth = AuthManager()
    return auth.verify_admin_password(password)
