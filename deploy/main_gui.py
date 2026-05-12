"""
亚马逊账单清洗工具 - 桌面GUI版本
使用 tkinter 构建图形界面
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import sys
import os
from pathlib import Path
from datetime import datetime
import hashlib
import traceback
import pandas as pd

# 全局错误捕获
def handle_exception(exc_type, exc_value, exc_traceback):
    """捕获未处理的异常"""
    error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    error_file = Path.home() / "BillCleaner" / "logs" / "crash.log"
    error_file.parent.mkdir(parents=True, exist_ok=True)
    with open(error_file, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*50}\n{datetime.now()}\n{error_msg}\n")
    messagebox.showerror("程序错误", f"程序出错，已记录到: {error_file}\n\n错误: {exc_value}")

sys.excepthook = handle_exception

# 获取exe所在目录
if getattr(sys, 'frozen', False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent

# 用户数据目录
if sys.platform == 'win32':
    USER_DATA_DIR = Path(os.environ.get('APPDATA', os.path.expanduser('~'))) / "BillCleaner"
else:
    USER_DATA_DIR = Path.home() / ".billcleaner"

USER_MAPPINGS_DIR = USER_DATA_DIR / "mappings"
USER_OUTPUT_DIR = USER_DATA_DIR / "output"
LOGS_DIR = USER_DATA_DIR / "logs"

# 程序目录
MAPPINGS_DIR = APP_DIR / "mappings_config"
INPUT_DIR = APP_DIR / "input"
OUTPUT_DIR = USER_OUTPUT_DIR

# 确保目录存在
for d in [USER_MAPPINGS_DIR, USER_OUTPUT_DIR, LOGS_DIR, INPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 添加路径
sys.path.insert(0, str(APP_DIR))

try:
    from core.auth import AuthManager
    from core.config_sync import sync_configs_on_startup
    from core.version_checker import check_version_on_startup
except ImportError as e:
    print(f"导入模块失败: {e}")


class LoginWindow:
    """登录窗口"""
    
    def __init__(self, master):
        self.master = master
        self.master.title("亚马逊账单清洗工具 - 登录")
        self.master.geometry("400x300")
        self.master.resizable(False, False)
        
        # 居中显示
        self.center_window(400, 300)
        
        self.auth_manager = AuthManager()
        self.current_user = None
        
        self.create_widgets()
        
        # 启动时同步配置
        self.sync_configs()
    
    def center_window(self, width, height):
        """窗口居中"""
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.master.geometry(f"{width}x{height}+{x}+{y}")
    
    def create_widgets(self):
        """创建界面组件"""
        # 标题
        title_frame = ttk.Frame(self.master, padding=20)
        title_frame.pack(fill=tk.X)
        
        ttk.Label(title_frame, text="亚马逊账单清洗工具", 
                  font=("Microsoft YaHei", 16, "bold")).pack()
        ttk.Label(title_frame, text="v2.0", font=("Microsoft YaHei", 10)).pack()
        
        # 登录表单
        form_frame = ttk.Frame(self.master, padding=30)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # 手机号
        ttk.Label(form_frame, text="手机号:", font=("Microsoft YaHei", 10)).grid(
            row=0, column=0, sticky=tk.W, pady=10)
        self.phone_entry = ttk.Entry(form_frame, width=25, font=("Microsoft YaHei", 10))
        self.phone_entry.grid(row=0, column=1, pady=10, padx=10)
        self.phone_entry.focus()
        
        # 密码
        ttk.Label(form_frame, text="密码:", font=("Microsoft YaHei", 10)).grid(
            row=1, column=0, sticky=tk.W, pady=10)
        
        pwd_frame = ttk.Frame(form_frame)
        pwd_frame.grid(row=1, column=1, pady=10, padx=10, sticky=tk.W)
        
        self.password_entry = ttk.Entry(pwd_frame, width=25, show="*", 
                                         font=("Microsoft YaHei", 10))
        self.password_entry.pack(side=tk.LEFT)
        self.password_entry.bind("<Return>", lambda e: self.login())
        
        # 密码可见切换按钮
        self.show_pwd_var = tk.BooleanVar()
        self.show_pwd_btn = ttk.Checkbutton(pwd_frame, variable=self.show_pwd_var,
                                             command=self.toggle_password)
        self.show_pwd_btn.pack(side=tk.LEFT, padx=5)
        
        # 按钮
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=20)
        
        ttk.Button(btn_frame, text="登录", width=15, 
                   command=self.login).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="退出", width=15, 
                   command=self.master.quit).pack(side=tk.LEFT, padx=10)
        
        # 提示
        ttk.Label(self.master, text="提示：账号由管理员统一分配", 
                  font=("Microsoft YaHei", 9), foreground="gray").pack(side=tk.BOTTOM, pady=10)
    
    def sync_configs(self):
        """异步同步配置（不阻塞窗口显示）"""
        def do_sync():
            try:
                sync_configs_on_startup(APP_DIR, silent=True)
            except Exception as e:
                print(f"配置同步失败: {e}")
        
        # 在后台线程执行，不阻塞UI
        import threading
        thread = threading.Thread(target=do_sync, daemon=True)
        thread.start()
    
    def toggle_password(self):
        """切换密码显示/隐藏"""
        if self.show_pwd_var.get():
            self.password_entry.config(show="")
        else:
            self.password_entry.config(show="*")
    
    def login(self):
        """登录"""
        phone = self.phone_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not phone:
            messagebox.showwarning("提示", "请输入手机号")
            return
        if not password:
            messagebox.showwarning("提示", "请输入密码")
            return
        
        # 验证登录
        success, message, remaining_days = self.auth_manager.login(phone, password)
        
        if success:
            self.current_user = phone
            
            # 显示欢迎消息和剩余天数
            if remaining_days is not None:
                if remaining_days <= 7:
                    # 剩余天数少于7天，红色警告
                    messagebox.showwarning("登录成功", 
                        f"{message}\n\n⚠️ 账号即将到期，剩余 {remaining_days} 天")
                else:
                    messagebox.showinfo("登录成功", 
                        f"{message}\n\n📅 账号有效期剩余 {remaining_days} 天")
            else:
                messagebox.showinfo("成功", message)
            
            self.open_main_window()
        else:
            messagebox.showerror("登录失败", message)
    
    def open_main_window(self):
        """打开主窗口"""
        self.master.withdraw()  # 隐藏登录窗口
        
        # 获取剩余天数
        accounts = self.auth_manager.load_accounts()
        remaining_days = None
        for user in accounts.get("users", []):
            if user.get("phone") == self.current_user:
                end_time = user.get("end_time", "")
                if end_time:
                    from datetime import datetime
                    end_date = datetime.strptime(end_time, "%Y-%m-%d")
                    remaining_days = (end_date - datetime.now()).days
                break
        
        main_window = tk.Toplevel()
        MainWindow(main_window, self.current_user, self.master, remaining_days)


class MainWindow:
    """主窗口"""
    
    def __init__(self, master, username, login_window, remaining_days=None):
        self.master = master
        self.login_window = login_window
        self.username = username
        self.remaining_days = remaining_days
        
        self.master.title(f"亚马逊账单清洗工具 - {username}")
        self.master.geometry("800x600")
        self.center_window(800, 600)
        
        # 关闭时返回登录
        self.master.protocol("WM_DELETE_WINDOW", self.logout)
        
        self.processing = False
        self.create_widgets()
    
    def center_window(self, width, height):
        """窗口居中"""
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.master.geometry(f"{width}x{height}+{x}+{y}")
    
    def create_widgets(self):
        """创建界面组件"""
        # 菜单栏
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)
        
        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="选择文件", command=self.select_file)
        file_menu.add_command(label="选择文件夹", command=self.select_folder)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.logout)
        
        # 工具菜单
        tool_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tool_menu)
        tool_menu.add_command(label="商品映射表维护", command=self.open_product_mapping)
        tool_menu.add_command(label="打开输出目录", command=self.open_output_dir)
        
        # 主框架
        main_frame = ttk.Frame(self.master, padding=5)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建Notebook选项卡
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # 选项卡1：账单清洗
        try:
            self.clean_frame = ttk.Frame(self.notebook)
            self.notebook.add(self.clean_frame, text="账单清洗")
            self._create_clean_tab(self.clean_frame)
        except Exception as e:
            print(f"[ERROR] 创建账单清洗tab失败: {e}")
            import traceback; traceback.print_exc()
        
        # 选项卡2：数据管理
        try:
            self.data_frame = ttk.Frame(self.notebook)
            self.notebook.add(self.data_frame, text="数据管理")
            self._create_data_tab(self.data_frame)
        except Exception as e:
            print(f"[ERROR] 创建数据管理tab失败: {e}")
            import traceback; traceback.print_exc()
        
        # 选项卡3：对账报表
        try:
            self.report_frame = ttk.Frame(self.notebook)
            self.notebook.add(self.report_frame, text="对账报表")
            self._create_report_tab(self.report_frame)
        except Exception as e:
            print(f"[ERROR] 创建对账报表tab失败: {e}")
            import traceback; traceback.print_exc()
        
        # 选项卡4：生成报表
        try:
            self.generator_frame = ttk.Frame(self.notebook)
            self.notebook.add(self.generator_frame, text="生成报表")
            self._create_report_generator_tab(self.generator_frame)
        except Exception as e:
            print(f"[ERROR] 创建生成报表tab失败: {e}")
            import traceback; traceback.print_exc()
        
        # 选项卡5：财务凭证
        try:
            self.voucher_frame = ttk.Frame(self.notebook)
            self.notebook.add(self.voucher_frame, text="财务凭证")
            self._create_voucher_tab(self.voucher_frame)
        except Exception as e:
            print(f"[ERROR] 创建财务凭证tab失败: {e}")
            import traceback; traceback.print_exc()
    
    def _create_clean_tab(self, parent):
        """创建账单清洗选项卡"""
        # 左侧操作区
        left_frame = ttk.LabelFrame(parent, text="操作", padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 文件选择
        file_frame = ttk.Frame(left_frame)
        file_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(file_frame, text="选择文件:").pack(side=tk.LEFT)
        self.file_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.file_path_var, width=40).pack(
            side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(file_frame, text="浏览...", command=self.select_file).pack(side=tk.LEFT)
        
        # 操作按钮
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=20)
        
        ttk.Button(btn_frame, text="开始清洗", width=15, 
                   command=self.start_clean).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="批量清洗", width=15, 
                   command=self.batch_clean).pack(side=tk.LEFT, padx=5)
        
        # 汇率管理按钮 - 单独保护
        try:
            ttk.Button(btn_frame, text="汇率管理", width=15, 
                       command=self.open_exchange_rate_manager).pack(side=tk.LEFT, padx=5)
        except Exception as e:
            print(f"[WARN] 汇率管理按钮创建失败: {e}")
        
        # 进度条 - 单独保护
        try:
            self.progress_var = tk.DoubleVar()
            self.progress = ttk.Progressbar(left_frame, variable=self.progress_var, maximum=100)
            self.progress.pack(fill=tk.X, pady=10)
        except Exception as e:
            print(f"[WARN] 进度条创建失败: {e}")
            self.progress_var = tk.DoubleVar()
        
        # 状态标签 - 单独保护
        try:
            self.status_var = tk.StringVar(value="就绪")
            ttk.Label(left_frame, textvariable=self.status_var, 
                      font=("Microsoft YaHei", 9)).pack(anchor=tk.W)
        except Exception as e:
            print(f"[WARN] 状态标签创建失败: {e}")
            self.status_var = tk.StringVar(value="就绪")
        
        # 日志区域 - 单独保护
        try:
            log_frame = ttk.LabelFrame(left_frame, text="处理日志", padding=5)
            log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
            
            self.log_text = tk.Text(log_frame, height=15, font=("Consolas", 9))
            self.log_text.pack(fill=tk.BOTH, expand=True)
            
            scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
            self.log_text.config(yscrollcommand=scrollbar.set)
        except Exception as e:
            print(f"[WARN] 日志区域创建失败: {e}")
            # 创建一个空的 log_text 以避免后续方法调用报错
            self.log_text = tk.Text(left_frame, height=5)
        
        # 右侧信息区 - 单独保护
        try:
            right_frame = ttk.LabelFrame(parent, text="信息", padding=10)
            right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
            
            # 用户信息
            info_frame = ttk.Frame(right_frame)
            info_frame.pack(fill=tk.X)
            
            ttk.Label(info_frame, text="当前用户:", font=("Microsoft YaHei", 9)).pack(anchor=tk.W)
            ttk.Label(info_frame, text=self.username, font=("Microsoft YaHei", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
            
            # 显示剩余天数
            if self.remaining_days is not None:
                if self.remaining_days <= 7:
                    days_text = f"⚠️ 剩余 {self.remaining_days} 天"
                    days_color = "red"
                else:
                    days_text = f"📅 剩余 {self.remaining_days} 天"
                    days_color = "green"
                ttk.Label(info_frame, text=days_text, font=("Microsoft YaHei", 9), 
                          foreground=days_color).pack(anchor=tk.W, pady=(0, 10))
            else:
                ttk.Label(info_frame, text="有效期: 永久", font=("Microsoft YaHei", 9), 
                          foreground="gray").pack(anchor=tk.W, pady=(0, 10))
            
            ttk.Label(info_frame, text="数据目录:", font=("Microsoft YaHei", 9)).pack(anchor=tk.W)
            ttk.Label(info_frame, text=str(USER_DATA_DIR), font=("Microsoft YaHei", 8), 
                      foreground="gray", wraplength=150).pack(anchor=tk.W)
            
            # 快捷操作
            ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
            
            ttk.Button(right_frame, text="🔄 检查更新", width=18, 
                       command=self.check_update).pack(pady=5)
            ttk.Button(right_frame, text="📦 商品映射表维护", width=18, 
                       command=self.open_product_mapping).pack(pady=5)
            ttk.Button(right_frame, text="📁 打开输出目录", width=18, 
                       command=self.open_output_dir).pack(pady=5)
            ttk.Button(right_frame, text="🚪 退出登录", width=18, 
                       command=self.logout).pack(pady=5)
        except Exception as e:
            print(f"[WARN] 右侧信息区创建失败: {e}")
            import traceback; traceback.print_exc()


    def _create_data_tab(self, parent):
        """创建数据管理选项卡（v1.3.0改进：复选框+导入进度）"""
        # 顶部工具栏
        toolbar = ttk.Frame(parent, padding=10)
        toolbar.pack(fill=tk.X)
        
        ttk.Label(toolbar, text="已清洗文件列表:", font=("Microsoft YaHei", 10, "bold")).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="刷新列表", command=self.refresh_file_list).pack(side=tk.RIGHT, padx=5)
        ttk.Button(toolbar, text="导入勾选", command=self.import_checked).pack(side=tk.RIGHT, padx=5)
        ttk.Button(toolbar, text="全不选", command=self.deselect_all_folders).pack(side=tk.RIGHT, padx=5)
        ttk.Button(toolbar, text="全选", command=self.select_all_folders).pack(side=tk.RIGHT, padx=5)
        
        # 文件列表（带复选框和导入状态）
        list_frame = ttk.LabelFrame(parent, text="待导入文件", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建带复选框的Treeview
        columns = ('选择', '文件名', '站点', '结算周期', '店铺', '导入状态')
        self.file_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.file_tree.heading(col, text=col)
            self.file_tree.column(col, width=80)
        
        self.file_tree.column('选择', width=50, anchor='center')
        self.file_tree.column('文件名', width=220)
        self.file_tree.column('站点', width=50, anchor='center')
        self.file_tree.column('结算周期', width=70, anchor='center')
        self.file_tree.column('店铺', width=100)
        self.file_tree.column('导入状态', width=100, anchor='center')
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=scrollbar.set)
        
        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 点击复选框列切换勾选状态
        self.file_tree.bind('<ButtonRelease-1>', self._on_file_tree_click)
        
        # 文件夹勾选状态字典: folder_name -> bool
        self.folder_checked = {}
        # 文件夹导入状态字典: folder_name -> str ('待导入','正在导入...','✓ 已成功','✗ 失败')
        self.folder_import_status = {}
        # 导入进行中标记
        self._importing = False
        
        # 已导入列表 - 三级树形结构
        imported_frame = ttk.LabelFrame(parent, text="已导入数据", padding=5)
        imported_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建树形结构（第一层：站点，第二层：店铺，第三层：具体数据）
        self.imported_tree = ttk.Treeview(imported_frame, show='tree', height=8)
        self.imported_tree.column('#0', width=350)  # 设置树列宽度
        
        scrollbar2 = ttk.Scrollbar(imported_frame, orient=tk.VERTICAL, command=self.imported_tree.yview)
        self.imported_tree.configure(yscrollcommand=scrollbar2.set)
        
        self.imported_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar2.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 底部操作按钮
        bottom_frame = ttk.Frame(parent, padding=10)
        bottom_frame.pack(fill=tk.X)
        
        ttk.Button(bottom_frame, text="删除选中", command=self.delete_selected).pack(side=tk.RIGHT, padx=5)
        
        # 导入日志
        log_frame = ttk.LabelFrame(parent, text="导入日志", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.import_log = tk.Text(log_frame, height=5, font=("Consolas", 9))
        self.import_log.pack(fill=tk.BOTH, expand=True)
        
        # 初始化数据库管理器
        from core.db_manager import DatabaseManager
        self.db = DatabaseManager(USER_DATA_DIR / "amazon_bills.db")
        
        # 刷新列表
        self.refresh_file_list()
    
    def _create_report_tab(self, parent):
        """创建对账报表选项卡"""
        # 顶部筛选栏
        filter_frame = ttk.Frame(parent, padding=10)
        filter_frame.pack(fill=tk.X)
        
        ttk.Label(filter_frame, text="结算周期:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.period_var = tk.StringVar()
        self.period_combo = ttk.Combobox(filter_frame, textvariable=self.period_var, width=12, state='readonly')
        self.period_combo.pack(side=tk.LEFT, padx=5)
        self.period_combo.bind('<<ComboboxSelected>>', lambda e: self._update_site_options())
        
        ttk.Label(filter_frame, text="站点:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(20, 0))
        self.site_var = tk.StringVar()
        self.site_combo = ttk.Combobox(filter_frame, textvariable=self.site_var, width=10, state='readonly')
        self.site_combo.pack(side=tk.LEFT, padx=5)
        self.site_combo.bind('<<ComboboxSelected>>', lambda e: self._update_shop_options())
        
        ttk.Label(filter_frame, text="店铺:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(20, 0))
        self.shop_var = tk.StringVar()
        self.shop_combo = ttk.Combobox(filter_frame, textvariable=self.shop_var, width=15, state='readonly')
        self.shop_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(filter_frame, text="查询报表", command=self.query_report).pack(side=tk.LEFT, padx=20)
        ttk.Button(filter_frame, text="刷新", command=self.refresh_report_options).pack(side=tk.LEFT)
        
        # 汇总区域
        summary_frame = ttk.LabelFrame(parent, text="汇总", padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 汇总标签
        self.summary_labels = {}
        summary_items = [('收入合计', '#90EE90'), ('费用合计', '#FFB6C1'), 
                         ('税费合计', '#87CEEB'), ('提现合计', '#DDA0DD')]
        
        for i, (name, color) in enumerate(summary_items):
            frame = ttk.Frame(summary_frame)
            frame.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
            
            ttk.Label(frame, text=name, font=("Microsoft YaHei", 9)).pack()
            label = ttk.Label(frame, text="0.00", font=("Microsoft YaHei", 14, "bold"))
            label.pack()
            self.summary_labels[name] = label
        
        # 明细区域（使用Notebook）
        detail_notebook = ttk.Notebook(parent)
        detail_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 四个明细表
        self.detail_trees = {}
        for category in ['收入明细', '费用明细', '税费明细', '提现明细']:
            frame = ttk.Frame(detail_notebook)
            detail_notebook.add(frame, text=category)
            
            # 创建表格
            tree_frame = ttk.Frame(frame)
            tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            columns = ('序列码', '项目', '借方金额', '贷方金额')
            tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
            
            tree.heading('序列码', text='序列码')
            tree.heading('项目', text='项目')
            tree.heading('借方金额', text='借方金额')
            tree.heading('贷方金额', text='贷方金额')
            
            tree.column('序列码', width=80, anchor='center')
            tree.column('项目', width=200)
            tree.column('借方金额', width=120, anchor='e')
            tree.column('贷方金额', width=120, anchor='e')
            
            scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            self.detail_trees[category] = tree
        
        # 初始化数据库管理器
        from core.db_manager import DatabaseManager
        if not hasattr(self, 'db'):
            self.db = DatabaseManager(USER_DATA_DIR / "amazon_bills.db")
        
        # 刷新选项
        self.refresh_report_options()
    
    def log(self, message):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
    
    def select_file(self):
        """选择文件"""
        file_path = filedialog.askopenfilename(
            title="选择账单文件",
            filetypes=[("CSV文件", "*.csv"), ("Excel文件", "*.xlsx"), ("所有文件", "*.*")],
            initialdir=str(INPUT_DIR)
        )
        if file_path:
            self.file_path_var.set(file_path)
            self.log(f"已选择: {Path(file_path).name}")
    
    def select_folder(self):
        """选择文件夹"""
        folder_path = filedialog.askdirectory(
            title="选择文件夹",
            initialdir=str(INPUT_DIR)
        )
        if folder_path:
            self.file_path_var.set(folder_path)
            self.log(f"已选择文件夹: {folder_path}")
    
    def start_clean(self):
        """开始清洗"""
        if self.processing:
            messagebox.showwarning("提示", "正在处理中，请等待...")
            return
        
        file_path = self.file_path_var.get()
        if not file_path:
            messagebox.showwarning("提示", "请先选择文件")
            return
        
        self.processing = True
        self.progress_var.set(0)
        self.status_var.set("处理中...")
        
        # 在后台线程执行
        thread = threading.Thread(target=self._do_clean, args=(file_path,))
        thread.daemon = True
        thread.start()
    
    def _do_clean(self, file_path):
        """执行清洗（后台线程）- 使用完整清洗引擎"""
        try:
            from core.bill_cleaner import BillCleaner
            import pandas as pd
            
            self.log("开始处理...")
            self.progress_var.set(5)
            
            # 初始化清洗引擎（加载所有映射表，支持本地汇率覆盖）
            self.log("初始化清洗引擎...")
            cleaner = BillCleaner(MAPPINGS_DIR, USER_DATA_DIR)
            self.progress_var.set(10)
            
            # 商品映射表路径
            product_mapping_file = USER_MAPPINGS_DIR / "product_mapping.csv"
            product_mapping_path = str(product_mapping_file) if product_mapping_file.exists() else None
            
            # 执行清洗（返回三个版本）
            self.log("执行清洗流程...")
            df_2d_usd, df_multi_dim, df_2d_local, report = cleaner.clean(file_path, product_mapping_path)
            self.progress_var.set(70)
            
            # 输出清洗报告
            for step in report.get('steps', []):
                self.log(f"  ✓ {step}")
            
            for warning in report.get('warnings', []):
                self.log(f"  ⚠ {warning}")
            
            self.progress_var.set(80)
            
            # 保存结果（v1.1.0改为文件夹结构）
            self.log("保存结果...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = Path(file_path).stem
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            
            # 创建子文件夹存放清洗结果
            result_folder = OUTPUT_DIR / base_name
            result_folder.mkdir(exist_ok=True)
            
            # 保存三个版本到子文件夹
            output_files = []
            
            # 1. 二维原币版本（v1.1.0优先保存，使用xlsxwriter引擎）
            output_2d_local = result_folder / f"{base_name}_二维原币版.xlsx"
            with pd.ExcelWriter(output_2d_local, engine='xlsxwriter') as writer:
                df_2d_local.to_excel(writer, index=False)
            self.log(f"  二维原币版: {output_2d_local.name}")
            output_files.append(output_2d_local)
            
            # 2. 二维美元版本
            output_2d_usd = result_folder / f"{base_name}_二维美元版.xlsx"
            with pd.ExcelWriter(output_2d_usd, engine='xlsxwriter') as writer:
                df_2d_usd.to_excel(writer, index=False)
            self.log(f"  二维美元版: {output_2d_usd.name}")
            output_files.append(output_2d_usd)
            
            # 3. 多维版本（宽表）
            output_multi = result_folder / f"{base_name}_多维版.xlsx"
            with pd.ExcelWriter(output_multi, engine='xlsxwriter') as writer:
                df_multi_dim.to_excel(writer, index=False)
            self.log(f"  多维版: {output_multi.name}")
            output_files.append(output_multi)
            
            self.progress_var.set(100)
            self.status_var.set("完成")
            self.log("✅ 处理完成!")
            
            # 统计信息
            self.log(f"\n📊 清洗统计:")
            self.log(f"  二维版本: {len(df_2d_usd)} 行")
            self.log(f"  多维版本: {len(df_multi_dim)} 行")
            if '中文意思' in df_2d_usd.columns:
                top_meanings = df_2d_usd['中文意思'].value_counts().head(5)
                self.log(f"  中文意思TOP5: {dict(top_meanings)}")
            if '结算周期' in df_2d_usd.columns:
                self.log(f"  结算周期: {df_2d_usd['结算周期'].unique().tolist()}")
            
            # 检查是否有未匹配项，生成汇总报告
            has_issues = self._generate_issue_report(report, base_name, timestamp, result_folder)
            
            # 显示结果
            if has_issues == True:
                self.master.after(0, lambda: messagebox.showwarning(
                    "完成但有异常", f"清洗完成，但发现未匹配项！\n\n二维版本: {len(df_2d_usd)} 行\n多维版本: {len(df_multi_dim)} 行\n\n⚠️ 请查看问题报告文件\n\n结果保存在:\n{output_2d_usd.parent}"))
            elif has_issues == 'sku_only':
                self.master.after(0, lambda: messagebox.showinfo(
                    "完成", f"清洗完成！\n\n二维版本: {len(df_2d_usd)} 行\n多维版本: {len(df_multi_dim)} 行\n\nℹ️ 商品匹配异常，请维护商品映射表，生成报表已可用\n\n结果保存在:\n{output_2d_usd.parent}"))
            else:
                self.master.after(0, lambda: messagebox.showinfo(
                    "完成", f"清洗完成！\n\n二维版本: {len(df_2d_usd)} 行\n多维版本: {len(df_multi_dim)} 行\n\n结果保存在:\n{output_2d_usd.parent}"))
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            self.log(f"❌ 错误: {e}")
            self.log(error_detail)
            self.status_var.set("失败")
            self.master.after(0, lambda: messagebox.showerror("错误", str(e)))
        
        finally:
            self.processing = False
    
    def batch_clean(self):
        """批量清洗（递归扫描子文件夹）"""
        folder_path = filedialog.askdirectory(
            title="选择包含CSV文件的文件夹（含子文件夹）",
            initialdir=str(INPUT_DIR)
        )
        if not folder_path:
            return
        
        # 递归扫描子文件夹
        csv_files = list(Path(folder_path).rglob("*.csv"))
        if not csv_files:
            messagebox.showwarning("提示", "该文件夹及其子文件夹没有CSV文件")
            return
        
        # 显示文件列表
        file_list = "\n".join([f"  - {f.relative_to(folder_path)}" for f in csv_files[:10]])
        if len(csv_files) > 10:
            file_list += f"\n  ... 还有 {len(csv_files) - 10} 个文件"
        
        if messagebox.askyesno("确认", f"找到 {len(csv_files)} 个CSV文件:\n{file_list}\n\n开始批量处理？"):
            self._do_batch_clean(csv_files, folder_path)
    
    def _do_batch_clean(self, csv_files: list, folder_path):
        """执行批量清洗"""
        import threading
        
        def process():
            from core.bill_cleaner import BillCleaner
            
            self.processing = True
            self.progress_var.set(0)
            self.status_var.set("批量清洗中...")
            
            success_count = 0
            fail_count = 0
            issue_count = 0
            
            product_mapping_path = MAPPINGS_DIR / "product_mapping.csv"
            cleaner = BillCleaner(MAPPINGS_DIR)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            
            # 生成汇总报告文件 - 使用dict去重，key为匹配辅助列/匹配key，记录来源文件
            all_issues = {
                'column_names': {},       # col -> set(来源文件名)
                'chinese_meanings': {},   # key -> {详情dict, 包含出现次数, 来源文件: set()}
                'performance_dimensions': {},  # key -> {详情dict, 包含出现次数, 来源文件: set()}
                'product_skus': {},       # sku -> set(来源文件名)
                'exchange_rates': {}      # rate -> set(来源文件名)
            }
            
            total = len(csv_files)
            
            for idx, csv_file in enumerate(csv_files):
                try:
                    self.log(f"\n[{idx+1}/{total}] 处理: {csv_file.name}")
                    self.progress_var.set(int((idx / total) * 100))
                    
                    # 清洗（v1.1.0返回df_2d_local）
                    df_2d_usd, df_multi_dim, df_2d_local, report = cleaner.clean(str(csv_file), str(product_mapping_path) if product_mapping_path.exists() else None)
                    
                    # 保存三个版本到子文件夹（v1.1.0文件夹结构）
                    base_name = csv_file.stem
                    result_folder = OUTPUT_DIR / base_name
                    result_folder.mkdir(exist_ok=True)
                    
                    # 1. 二维原币版本
                    output_2d_local = result_folder / f"{base_name}_二维原币版.xlsx"
                    with pd.ExcelWriter(output_2d_local, engine='xlsxwriter') as writer:
                        df_2d_local.to_excel(writer, index=False)
                    
                    # 2. 二维美元版本
                    output_2d_usd = result_folder / f"{base_name}_二维美元版.xlsx"
                    with pd.ExcelWriter(output_2d_usd, engine='xlsxwriter') as writer:
                        df_2d_usd.to_excel(writer, index=False)
                    
                    # 3. 多维版本
                    output_multi = result_folder / f"{base_name}_多维版.xlsx"
                    with pd.ExcelWriter(output_multi, engine='xlsxwriter') as writer:
                        df_multi_dim.to_excel(writer, index=False)
                    
                    self.log(f"  ✓ 完成: {len(df_2d_usd)} 行")
                    
                    # 收集问题 - chinese_meanings和performance_dimensions用dict去重，记录来源文件
                    unmatched = report.get('unmatched', {})
                    source_file = csv_file.name
                    for col in unmatched.get('column_names', []):
                        if col not in all_issues['column_names']:
                            all_issues['column_names'][col] = set()
                        all_issues['column_names'][col].add(source_file)
                    for item in unmatched.get('chinese_meanings', []):
                        if isinstance(item, dict):
                            key = item.get('匹配辅助列', str(item))
                            count = item.get('出现次数', 1)
                            if key in all_issues['chinese_meanings']:
                                all_issues['chinese_meanings'][key]['出现次数'] = all_issues['chinese_meanings'][key].get('出现次数', 0) + count
                                all_issues['chinese_meanings'][key].setdefault('来源文件', set()).add(source_file)
                            else:
                                all_issues['chinese_meanings'][key] = dict(item)
                                all_issues['chinese_meanings'][key]['来源文件'] = {source_file}
                        else:
                            s = str(item)
                            if s not in all_issues['chinese_meanings']:
                                all_issues['chinese_meanings'][s] = {'匹配辅助列': s, '出现次数': 1, '来源文件': {source_file}}
                            else:
                                all_issues['chinese_meanings'][s].setdefault('来源文件', set()).add(source_file)
                    for item in unmatched.get('performance_dimensions', []):
                        if isinstance(item, dict):
                            key = item.get('匹配key', str(item))
                            count = item.get('出现次数', 1)
                            if key in all_issues['performance_dimensions']:
                                all_issues['performance_dimensions'][key]['出现次数'] = all_issues['performance_dimensions'][key].get('出现次数', 0) + count
                                all_issues['performance_dimensions'][key].setdefault('来源文件', set()).add(source_file)
                            else:
                                all_issues['performance_dimensions'][key] = dict(item)
                                all_issues['performance_dimensions'][key]['来源文件'] = {source_file}
                        else:
                            s = str(item)
                            if s not in all_issues['performance_dimensions']:
                                all_issues['performance_dimensions'][s] = {'匹配key': s, '出现次数': 1, '来源文件': {source_file}}
                            else:
                                all_issues['performance_dimensions'][s].setdefault('来源文件', set()).add(source_file)
                    for sku in unmatched.get('product_skus', []):
                        if sku not in all_issues['product_skus']:
                            all_issues['product_skus'][sku] = set()
                        all_issues['product_skus'][sku].add(source_file)
                    for item in unmatched.get('exchange_rates', []):
                        if item not in all_issues['exchange_rates']:
                            all_issues['exchange_rates'][item] = set()
                        all_issues['exchange_rates'][item].add(source_file)
                    
                    # 判断是否有非SKU的问题（只有SKU未匹配不算异常）
                    has_non_sku_issues = any([
                        unmatched.get('column_names'),
                        unmatched.get('chinese_meanings'),
                        unmatched.get('performance_dimensions'),
                        unmatched.get('exchange_rates')
                    ])
                    has_any_issues = has_non_sku_issues or bool(unmatched.get('product_skus'))
                    
                    if has_non_sku_issues:
                        issue_count += 1
                    elif has_any_issues:
                        # 只有SKU问题，不计入issue_count但仍然记录
                        pass
                    
                    success_count += 1
                    
                except Exception as e:
                    self.log(f"  ✗ 失败: {e}")
                    fail_count += 1
            
            # 生成汇总问题报告
            # 只有SKU问题不算异常
            has_non_sku_issues = any([
                all_issues['column_names'],
                all_issues['chinese_meanings'],
                all_issues['performance_dimensions'],
                all_issues['exchange_rates']
            ])
            has_issues = any(all_issues.values())
            has_sku_only_issues = bool(all_issues['product_skus']) and not has_non_sku_issues
            if has_issues:
                report_file = OUTPUT_DIR / f"批量清洗问题汇总_{timestamp}.txt"
                with open(report_file, 'w', encoding='utf-8') as f:
                    f.write("=" * 60 + "\n")
                    f.write("批量清洗问题汇总报告\n")
                    f.write("=" * 60 + "\n\n")
                    f.write(f"清洗时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"总文件数: {total}\n")
                    if has_sku_only_issues:
                        f.write(f"成功: {success_count}, 失败: {fail_count}\n")
                        f.write("状态: ℹ️ 商品匹配异常，请维护商品映射表，生成报表已可用\n\n")
                    else:
                        f.write(f"成功: {success_count}, 失败: {fail_count}, 有问题: {issue_count}\n")
                        f.write("状态: ⚠️ 发现异常\n\n")
                    
                    if all_issues['column_names']:
                        f.write("=" * 60 + "\n")
                        f.write("一、未翻译的列名\n")
                        f.write("=" * 60 + "\n")
                        f.write("[需维护 column_name_full_mapping.csv]\n\n")
                        f.write("格式: 原始列名,中文列名\n")
                        f.write("示例: Transaction Status,交易状态\n\n")
                        for col, sources in all_issues['column_names'].items():
                            col_display = col[:80] + "..." if len(col) > 80 else col
                            source_str = ", ".join(sorted(sources))
                            f.write(f"- {col_display}\n  📄 来源: {source_str}\n")
                        f.write("\n")
                    
                    if all_issues['chinese_meanings']:
                        f.write("=" * 60 + "\n")
                        f.write("二、未匹配的中文意思\n")
                        f.write("=" * 60 + "\n")
                        f.write("[需维护 chinese_meaning_mapping.csv]\n")
                        f.write("格式: 匹配辅助列,中文意思\n")
                        f.write("示例: US_Product charges_Commission,产品佣金\n\n")
                        f.write("【每种类型只显示一条样例，按出现次数降序排列，跨文件累加次数】\n\n")
                        # 按出现次数降序排列
                        sorted_items = sorted(all_issues['chinese_meanings'].values(), key=lambda x: x.get('出现次数', 0), reverse=True)
                        for item in sorted_items:
                            helper_key = item.get('匹配辅助列', '')
                            count = item.get('出现次数', 1)
                            source_files = item.get('来源文件', set())
                            source_str = ", ".join(sorted(source_files)) if source_files else "未知"
                            f.write(f"- {helper_key} (出现 {count} 次)\n  📄 来源: {source_str}\n")
                            for k, v in item.items():
                                if k not in ('匹配辅助列', '出现次数', '来源文件') and v:
                                    f.write(f"  {k}: {v}\n")
                            f.write("\n")
                        f.write("\n")
                    
                    if all_issues['performance_dimensions']:
                        f.write("=" * 60 + "\n")
                        f.write("三、未匹配的绩效维度\n")
                        f.write("=" * 60 + "\n")
                        f.write("[需维护 performance_dimension_mapping.csv]\n")
                        f.write("格式: 站点,二维匹配列-1,二维匹配列-2,中文意思,账单字段序列,维度,绩效表对应维度\n")
                        f.write("示例: US,优惠活动报名费,佣金,优惠活动报名费,33,推广费,推广费\n\n")
                        f.write("【每种类型只显示一条样例，按出现次数降序排列，跨文件累加次数】\n\n")
                        # 按出现次数降序排列
                        sorted_items = sorted(all_issues['performance_dimensions'].values(), key=lambda x: x.get('出现次数', 0), reverse=True)
                        for item in sorted_items:
                            perf_key = item.get('匹配key', '')
                            count = item.get('出现次数', 1)
                            helper_val = item.get('匹配辅助列', '')
                            source_files = item.get('来源文件', set())
                            source_str = ", ".join(sorted(source_files)) if source_files else "未知"
                            # 在匹配key后追加匹配辅助列原始值，方便一眼看出哪个匹配列没匹配上中文意思
                            helper_info = f" (匹配辅助列: {helper_val})" if helper_val else ""
                            f.write(f"- {perf_key}{helper_info} (出现 {count} 次)\n  📄 来源: {source_str}\n")
                            for k, v in item.items():
                                if k not in ('匹配key', '出现次数', '来源文件') and v:
                                    f.write(f"  {k}: {v}\n")
                            f.write("\n")
                        f.write("\n")
                    
                    if all_issues['product_skus']:
                        f.write("=" * 60 + "\n")
                        f.write("四、未匹配的商品SKU\n")
                        f.write("=" * 60 + "\n")
                        f.write("[需维护 product_mapping.csv]\n\n")
                        f.write("格式: SKU,商品名称,成本(USD),备注\n")
                        f.write("示例: B08ABC123,iPhone手机壳,2.50,爆款商品\n\n")
                        for sku, sources in sorted(all_issues['product_skus'].items()):
                            source_str = ", ".join(sorted(sources))
                            f.write(f"- {sku}\n  📄 来源: {source_str}\n")
                        f.write("\n")
                    
                    if all_issues['exchange_rates']:
                        f.write("=" * 60 + "\n")
                        f.write("五、未匹配的汇率\n")
                        f.write("=" * 60 + "\n")
                        f.write("[需维护 exchange_rates.csv]\n\n")
                        f.write("格式: 币种,汇率,更新日期\n")
                        f.write("示例: EUR,1.08,2026-04-21\n\n")
                        for item, sources in all_issues['exchange_rates'].items():
                            source_str = ", ".join(sorted(sources))
                            f.write(f"- {item}\n  📄 来源: {source_str}\n")
                        f.write("\n")
                    
                    f.write("=" * 60 + "\n")
                    f.write("维护指南\n")
                    f.write("=" * 60 + "\n\n")
                    f.write("程序启动时会自动拉取最新配置。\n")
                
                self.log(f"\n⚠️ 已生成汇总报告: {report_file.name}")
            
            self.progress_var.set(100)
            self.status_var.set("完成")
            self.log(f"\n✅ 批量清洗完成！成功: {success_count}, 失败: {fail_count}, 有问题: {issue_count}")
            
            if has_issues and not has_sku_only_issues:
                self.master.after(0, lambda: messagebox.showwarning(
                    "完成但有异常", f"批量清洗完成！\n\n成功: {success_count}\n失败: {fail_count}\n有问题: {issue_count}\n\n⚠️ 请查看汇总报告文件"))
            elif has_sku_only_issues:
                self.master.after(0, lambda: messagebox.showinfo(
                    "完成", f"批量清洗完成！\n\n成功: {success_count}\n失败: {fail_count}\n\nℹ️ 商品匹配异常，请维护商品映射表，生成报表已可用"))
            else:
                self.master.after(0, lambda: messagebox.showinfo(
                    "完成", f"批量清洗完成！\n\n成功: {success_count}\n失败: {fail_count}\n\n结果保存在:\n{OUTPUT_DIR}"))
            
            self.processing = False
        
        thread = threading.Thread(target=process)
        thread.daemon = True
        thread.start()
    
    # ==================== 数据管理相关方法 ====================
    
    def refresh_file_list(self):
        """刷新待导入文件列表（v1.3.0改进：带复选框和导入状态）"""
        # 保存当前勾选状态（刷新前）
        old_checked = dict(self.folder_checked) if hasattr(self, 'folder_checked') else {}
        old_status = dict(self.folder_import_status) if hasattr(self, 'folder_import_status') else {}
        
        # 清空列表
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        
        for item in self.imported_tree.get_children():
            self.imported_tree.delete(item)
        
        # 扫描output目录下的子文件夹（v1.1.0文件夹结构）
        folders = [d for d in OUTPUT_DIR.iterdir() if d.is_dir()]
        
        for folder in folders:
            # 从文件夹名解析站点、结算周期和店铺名称
            folder_name = folder.name
            
            # 尝试解析
            site = ''
            period = ''
            shop_name = ''
            try:
                import re
                # 格式: 结算周期(6位) + 站点(2位) + 明细- + 店铺名称
                match = re.match(r'^(\d{6})([A-Z]{2})明细[-_](.+)$', folder_name)
                if match:
                    period = match.group(1)
                    site = match.group(2)
                    shop_name = match.group(3)
                else:
                    # 兼容旧格式：没有店铺名称
                    match = re.match(r'^(\d{6})([A-Z]{2})', folder_name)
                    if match:
                        period = match.group(1)
                        site = match.group(2)
            except:
                pass
            
            # 检查是否已导入
            is_imported = site and period and self.db.check_exists(site, period, shop_name)
            
            # 恢复勾选状态（新出现的文件夹默认不勾选）
            checked = old_checked.get(folder_name, False)
            self.folder_checked[folder_name] = checked
            
            # 恢复导入状态（已导入的刷新后显示已导入，否则恢复上次状态）
            if is_imported:
                import_status = '✓ 已导入'
            else:
                import_status = old_status.get(folder_name, '待导入')
            self.folder_import_status[folder_name] = import_status
            
            # 勾选标记
            check_mark = '☑' if checked else '☐'
            
            # 状态显示列
            status_display = import_status
            
            self.file_tree.insert('', 'end', iid=folder_name, values=(
                check_mark,
                folder_name,
                site,
                period,
                shop_name,
                status_display
            ), tags=(import_status,))
        
        # 设置颜色标签
        self.file_tree.tag_configure('待导入', foreground='black')
        self.file_tree.tag_configure('正在导入...', foreground='#E6A800', font=('Microsoft YaHei', 9, 'bold'))
        self.file_tree.tag_configure('✓ 已成功', foreground='green')
        self.file_tree.tag_configure('✗ 失败', foreground='red')
        self.file_tree.tag_configure('✓ 已导入', foreground='gray')
        
        # 加载已导入列表 - 三级树形结构：结算周期→站点→店铺
        settlements = self.db.get_settlements_list()
        
        # 按三级结构统计数量
        period_counts = {}    # period -> count
        site_counts = {}      # (period, site) -> count
        shop_counts = {}      # (period, site, shop) -> count
        shop_details = {}     # (period, site, shop) -> [detail texts]
        
        for s in settlements:
            period = s['settlement_period']
            site = s['site']
            shop = s.get('shop_name', '') or '默认'
            row_count = s['row_count']
            cleaned_at = s['cleaned_at'][:16] if s['cleaned_at'] else ''
            
            period_counts[period] = period_counts.get(period, 0) + 1
            site_counts[(period, site)] = site_counts.get((period, site), 0) + 1
            shop_counts[(period, site, shop)] = shop_counts.get((period, site, shop), 0) + 1
            
            key = (period, site, shop)
            if key not in shop_details:
                shop_details[key] = []
            shop_details[key].append(f"行数: {row_count}  |  导入时间: {cleaned_at}")
        
        # 构建树形结构
        for period in sorted(period_counts.keys(), reverse=True):
            period_node_id = f"period_{period}"
            period_text = f"{period} ({period_counts[period]})"
            self.imported_tree.insert('', 'end', iid=period_node_id, text=period_text, tags=('period',))
            
            # 该周期下的站点
            period_sites = sorted(set(s for (p, s) in site_counts.keys() if p == period))
            for site in period_sites:
                site_node_id = f"site_{period}_{site}"
                site_text = f"{site} ({site_counts[(period, site)]})"
                self.imported_tree.insert(period_node_id, 'end', iid=site_node_id, text=site_text, tags=('site',))
                
                # 该站点下的店铺
                period_site_shops = sorted(set(sh for (p, s, sh) in shop_counts.keys() if p == period and s == site))
                for shop in period_site_shops:
                    shop_node_id = f"shop_{period}_{site}_{shop}"
                    shop_text = f"{shop} ({shop_counts[(period, site, shop)]})"
                    self.imported_tree.insert(site_node_id, 'end', iid=shop_node_id, text=shop_text, tags=('shop',))
                    
                    # 店铺下的具体数据行
                    for idx, detail in enumerate(shop_details.get((period, site, shop), [])):
                        data_node_id = f"data_{period}_{site}_{shop}_{idx}"
                        data_text = f"  {detail}"
                        self.imported_tree.insert(shop_node_id, 'end', iid=data_node_id, text=data_text, tags=('data',))
        
        # 设置树形结构样式
        self.imported_tree.tag_configure('period', font=('Microsoft YaHei', 10, 'bold'))
        self.imported_tree.tag_configure('site', font=('Microsoft YaHei', 9, 'bold'))
        self.imported_tree.tag_configure('shop', font=('Microsoft YaHei', 9))
        self.imported_tree.tag_configure('data', font=('Microsoft YaHei', 8))
    
    def _on_file_tree_click(self, event):
        """点击文件列表时，判断是否点击了复选框列，切换勾选状态"""
        if self._importing:
            return  # 导入中不允许切换勾选
        
        region = self.file_tree.identify_region(event.x, event.y)
        column = self.file_tree.identify_column(event.x)
        
        if region == 'cell' and column == '#1':  # #1 = 第一列（选择列）
            item = self.file_tree.identify_row(event.y)
            if item:
                folder_name = item  # 使用folder_name作为iid
                # 切换勾选状态
                self.folder_checked[folder_name] = not self.folder_checked.get(folder_name, False)
                checked = self.folder_checked[folder_name]
                check_mark = '☑' if checked else '☐'
                # 更新显示
                values = list(self.file_tree.item(item, 'values'))
                values[0] = check_mark
                self.file_tree.item(item, values=values)
    
    def select_all_folders(self):
        """全选所有文件夹"""
        if self._importing:
            return
        for item in self.file_tree.get_children():
            folder_name = item
            self.folder_checked[folder_name] = True
            values = list(self.file_tree.item(item, 'values'))
            values[0] = '☑'
            self.file_tree.item(item, values=values)
    
    def deselect_all_folders(self):
        """全不选所有文件夹"""
        if self._importing:
            return
        for item in self.file_tree.get_children():
            folder_name = item
            self.folder_checked[folder_name] = False
            values = list(self.file_tree.item(item, 'values'))
            values[0] = '☐'
            self.file_tree.item(item, values=values)
    
    def import_checked(self):
        """导入勾选的文件夹（v1.3.0改进：基于复选框+线程导入+进度状态）"""
        if self._importing:
            messagebox.showwarning("提示", "正在导入中，请等待完成")
            return
        
        # 收集勾选的文件夹
        checked_folders = []
        for item in self.file_tree.get_children():
            folder_name = item
            if self.folder_checked.get(folder_name, False):
                values = self.file_tree.item(item, 'values')
                checked_folders.append({
                    'folder_name': folder_name,
                    'site': values[2],
                    'period': values[3],
                    'shop_name': values[4],
                    'import_status': values[5]
                })
        
        if not checked_folders:
            messagebox.showwarning("提示", "请先勾选要导入的文件夹\n（点击文件列表第一列的☐可切换勾选）")
            return
        
        # 检查是否有已导入的文件夹需要覆盖确认
        overwrite_folders = []
        import_folders = []
        for f in checked_folders:
            if f['import_status'] in ('✓ 已导入', '✓ 已成功'):
                overwrite_folders.append(f)
            else:
                import_folders.append(f)
        
        if overwrite_folders:
            folder_names = '\n'.join([f"  - {f['folder_name']}" for f in overwrite_folders])
            result = messagebox.askyesno(
                "确认覆盖",
                f"以下文件夹已导入，是否覆盖？\n（将删除原数据重新导入）\n{folder_names}"
            )
            if result:
                import_folders.extend(overwrite_folders)
            # 不覆盖的不导入
        
        if not import_folders:
            self._log_import("未选择需要导入的文件夹")
            return
        
        # 标记导入中
        self._importing = True
        
        # 在子线程中执行导入
        def do_import():
            success_count = 0
            fail_count = 0
            for f in import_folders:
                folder_name = f['folder_name']
                site = f['site']
                period = f['period']
                shop_name = f['shop_name'] if f['shop_name'] else None
                is_overwrite = f in overwrite_folders
                
                # 更新状态为"正在导入..."
                self.master.after(0, self._update_folder_status, folder_name, '正在导入...')
                
                try:
                    result = self._import_folder_sync(folder_name, site, period, shop_name, force_overwrite=is_overwrite)
                    if result:
                        success_count += 1
                        self.master.after(0, self._update_folder_status, folder_name, '✓ 已成功')
                    else:
                        fail_count += 1
                        self.master.after(0, self._update_folder_status, folder_name, '✗ 失败')
                except Exception as e:
                    fail_count += 1
                    self.master.after(0, self._update_folder_status, folder_name, '✗ 失败')
                    self.master.after(0, self._log_import, f"✗ {folder_name} 导入异常: {e}")
            
            # 导入完成
            self._importing = False
            self.master.after(0, self._log_import, f"导入完成：成功 {success_count} 个，失败 {fail_count} 个")
            # 刷新列表（在主线程）
            self.master.after(0, self.refresh_file_list)
        
        thread = threading.Thread(target=do_import, daemon=True)
        thread.start()
    
    def _update_folder_status(self, folder_name, status):
        """更新文件夹的导入状态显示（在主线程调用）"""
        self.folder_import_status[folder_name] = status
        try:
            item_id = folder_name
            if self.file_tree.exists(item_id):
                values = list(self.file_tree.item(item_id, 'values'))
                values[5] = status
                self.file_tree.item(item_id, values=values, tags=(status,))
        except Exception:
            pass  # 如果item已不存在（被refresh清掉），忽略
    
    def _import_folder_sync(self, folder_name: str, site: str, period: str, shop_name: str = None, force_overwrite: bool = False) -> bool:
        """导入单个文件夹到数据库（同步版本，在子线程调用）
        
        Args:
            folder_name: 文件夹名
            site: 站点
            period: 结算周期
            shop_name: 店铺名称
            force_overwrite: 是否强制覆盖
        
        Returns:
            bool: 导入是否成功
        """
        try:
            import pandas as pd
            
            folder_path = OUTPUT_DIR / folder_name
            shop_str = f" {shop_name}" if shop_name else ""
            
            # 检查是否已存在
            if self.db.check_exists(site, period, shop_name):
                if force_overwrite:
                    self.db.delete_settlement(site, period, shop_name)
                    self.master.after(0, self._log_import, f"删除旧数据: {site} {period}{shop_str}")
                else:
                    self.master.after(0, self._log_import, f"跳过: {folder_name} (已存在)")
                    return False
            
            imported_count = 0
            skip_count = 0
            
            # 1. 导入二维原币版本（必须存在）
            file_2d_local = folder_path / f"{folder_name}_二维原币版.xlsx"
            if file_2d_local.exists():
                df_2d_local = pd.read_excel(file_2d_local)
                success, msg = self.db.import_2d_local_dataframe(df_2d_local, site, period, file_2d_local.name, shop_name)
                if success:
                    self.master.after(0, self._log_import, f"✓ 二维原币版导入: {site} {period}{shop_str}，{len(df_2d_local)} 行")
                    imported_count += 1
                else:
                    self.master.after(0, self._log_import, f"✗ 二维原币版导入失败: {msg}")
            else:
                self.master.after(0, self._log_import, f"✗ 未找到二维原币版文件: {file_2d_local.name}，必须存在")
                skip_count += 1
            
            # 2. 导入二维美元版本（必须存在）
            file_2d_usd = folder_path / f"{folder_name}_二维美元版.xlsx"
            if file_2d_usd.exists():
                df_2d_usd = pd.read_excel(file_2d_usd)
                success, msg = self.db.import_dataframe(df_2d_usd, site, period, file_2d_usd.name, shop_name)
                if success:
                    self.master.after(0, self._log_import, f"✓ 二维美元版导入: {site} {period}{shop_str}，{len(df_2d_usd)} 行")
                    imported_count += 1
                else:
                    self.master.after(0, self._log_import, f"✗ 二维美元版导入失败: {msg}")
            else:
                self.master.after(0, self._log_import, f"✗ 未找到二维美元版文件: {file_2d_usd.name}，必须存在")
                skip_count += 1
            
            # 3. 导入多维版本（可选）
            file_multi = folder_path / f"{folder_name}_多维版.xlsx"
            if file_multi.exists():
                df_multi = pd.read_excel(file_multi)
                success, msg = self.db.import_multi_dataframe(df_multi, site, period, file_multi.name, shop_name)
                if success:
                    self.master.after(0, self._log_import, f"✓ 多维版导入: {site} {period}{shop_str}，{len(df_multi)} 行")
                else:
                    self.master.after(0, self._log_import, f"⚠ 多维版导入失败: {msg}")
            else:
                self.master.after(0, self._log_import, f"⚠ 未找到多维版文件: {file_multi.name}，跳过多维数据导入")
            
            if skip_count > 0:
                self.master.after(0, self._log_import, f"⚠ 导入不完整：缺少 {skip_count} 个必需文件")
            
            return skip_count == 0
            
        except Exception as e:
            self.master.after(0, self._log_import, f"✗ 导入失败: {e}")
            return False
    
    def import_selected(self):
        """导入选中的文件夹（v1.1.0改为文件夹导入，v1.3.0改为基于勾选）"""
        selected = self.file_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要导入的文件夹")
            return
        
        # 将选中的文件夹勾选
        for item in selected:
            folder_name = item
            self.folder_checked[folder_name] = True
            values = list(self.file_tree.item(item, 'values'))
            values[0] = '☑'
            self.file_tree.item(item, values=values)
        
        # 调用统一的导入方法
        self.import_checked()
    
    def import_all(self):
        """导入全部文件夹（v1.3.0改为全选+导入勾选）"""
        if self._importing:
            messagebox.showwarning("提示", "正在导入中，请等待完成")
            return
        self.select_all_folders()
        self.import_checked()
    
    def _log_import(self, message: str):
        """添加导入日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.import_log.insert(tk.END, f"[{timestamp}] {message}\n")
        self.import_log.see(tk.END)
    
    def delete_selected(self):
        """删除选中的已导入数据"""
        selected = self.imported_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要删除的数据")
            return
        
        period_items = []   # 一级：结算周期
        site_items = []     # 二级：站点 (period, site)
        shop_items = []     # 三级：店铺 (period, site, shop)
        data_items = []     # 四级：具体数据行
        
        for item in selected:
            item_id = item
            if item_id and item_id.startswith('period_'):
                # 一级节点：period_{period}
                period = item_id[len('period_'):]
                period_items.append(period)
            elif item_id and item_id.startswith('site_'):
                # 二级节点：site_{period}_{site}
                parts = item_id[len('site_'):].split('_', 1)
                if len(parts) == 2:
                    period, site = parts
                    site_items.append((period, site))
            elif item_id and item_id.startswith('shop_'):
                # 三级节点：shop_{period}_{site}_{shop}
                parts = item_id[len('shop_'):].split('_', 2)
                if len(parts) == 3:
                    period, site, shop = parts
                    shop_items.append((period, site, shop))
            elif item_id and item_id.startswith('data_'):
                # 四级节点：data_{period}_{site}_{shop}_{idx}
                parts = item_id[len('data_'):].rsplit('_', 1)
                if len(parts) == 2:
                    shop_key, idx = parts
                    shop_parts = shop_key.split('_', 2)
                    if len(shop_parts) == 3:
                        period, site, shop = shop_parts
                        data_items.append((period, site, shop))
        
        # 构建删除列表和确认信息
        delete_ops = []  # (type, label)
        
        for period in period_items:
            delete_ops.append(('period', f"结算周期 {period} 下所有数据", period, None, None))
        
        for period, site in site_items:
            delete_ops.append(('site', f"{period} / {site} 下所有店铺数据", period, site, None))
        
        for period, site, shop in shop_items:
            delete_ops.append(('shop', f"{period} / {site} / {shop}", period, site, shop))
        
        for period, site, shop in set(data_items):
            delete_ops.append(('shop', f"{period} / {site} / {shop}", period, site, shop))
        
        if not delete_ops:
            messagebox.showwarning("提示", "请选择要删除的数据")
            return
        
        # 构建确认信息
        confirm_lines = [f"确定要删除以下 {len(delete_ops)} 项数据吗？\n"]
        for dtype, label, _, _, _ in delete_ops:
            type_names = {'period': '🔄 按结算周期', 'site': '🌐 按站点', 'shop': '🏪 按店铺'}
            confirm_lines.append(f"  {type_names.get(dtype, '')} {label}")
        
        if not messagebox.askyesno("确认删除", '\n'.join(confirm_lines)):
            return
        
        # 执行删除
        for dtype, label, period, site, shop in delete_ops:
            if dtype == 'period':
                count = self.db.delete_settlements_by_period(period)
                self._log_import(f"删除结算周期 {period} 下所有数据（{count} 条）")
            elif dtype == 'site':
                count = self.db.delete_settlements_by_site_period(site, period)
                self._log_import(f"删除 {period}/{site} 下所有数据（{count} 条）")
            elif dtype == 'shop':
                shop_name = shop if shop != '默认' else None
                self.db.delete_settlement(site, period, shop_name)
                self._log_import(f"删除: {period}/{site}/{shop}")
        
        self.refresh_file_list()
    
    # ==================== 报表相关方法 ====================
    
    def refresh_report_options(self):
        """刷新报表筛选选项"""
        # 获取结算周期列表
        periods = self.db.get_periods()
        self.period_combo['values'] = periods
        
        if periods:
            self.period_combo.set(periods[0])
            self._update_site_options()
    
    def _update_site_options(self):
        """更新站点选项（选中结算周期后联动）"""
        period = self.period_var.get()
        if period:
            sites = self.db.get_sites_by_period(period)
            self.site_combo['values'] = sites
            if sites:
                self.site_combo.set(sites[0])
                self._update_shop_options()
    
    def _update_shop_options(self):
        """更新店铺选项"""
        period = self.period_var.get()
        site = self.site_var.get()
        if period and site:
            shops = self.db.get_shops(site, period)
            self.shop_combo['values'] = shops
            if shops:
                self.shop_combo.set(shops[0])
    
    def query_report(self):
        """查询报表"""
        site = self.site_var.get()
        period = self.period_var.get()
        shop_name = self.shop_var.get()
        
        if not site or not period:
            messagebox.showwarning("提示", "请选择站点和结算周期")
            return
        
        # 获取报表数据
        report = self.db.get_report_data(site, period, shop_name if shop_name else None)
        
        if not report:
            messagebox.showinfo("提示", f"未找到 {site} {period} {shop_name} 的数据")
            return
        
        # 更新汇总
        for name, value in report['summary'].items():
            self.summary_labels[name].config(text=f"{value:,.2f}")
        
        # 更新明细表
        for category in ['收入明细', '费用明细', '税费明细', '提现明细']:
            tree = self.detail_trees[category]
            
            # 清空
            for item in tree.get_children():
                tree.delete(item)
            
            # 填充数据
            details = report['details'].get(category, [])
            for d in details:
                tree.insert('', 'end', values=(
                    d['序列码'],
                    d['项目'],
                    f"{d['借方金额']:,.2f}",
                    f"{d['贷方金额']:,.2f}"
                ))
    
    def open_product_mapping(self):
        """打开商品映射表维护窗口"""
        ProductMappingWindow(self.master)
    
    def open_exchange_rate_manager(self):
        """打开汇率管理弹窗"""
        ExchangeRateManager(self.master, MAPPINGS_DIR, USER_DATA_DIR)
    
    def open_output_dir(self):
        """打开输出目录"""
        import subprocess
        subprocess.run(['explorer', str(OUTPUT_DIR)])
    
    def check_update(self):
        """检查更新"""
        self.log("正在检查更新...")
        
        # 强制更新配置
        def do_update():
            try:
                # 删除版本缓存
                version_file = MAPPINGS_DIR / ".version"
                if version_file.exists():
                    version_file.unlink()
                
                # 重新同步
                sync_configs_on_startup(APP_DIR)
                self.log("✅ 配置更新完成！")
                self.master.after(0, lambda: messagebox.showinfo(
                    "更新完成", "配置已更新到最新版本！\n\n包含：\n- 列名映射\n- 汇率表\n- 匹配规则\n- 用户账号"))
            except Exception as e:
                self.log(f"❌ 更新失败: {e}")
                self.master.after(0, lambda: messagebox.showerror(
                    "更新失败", str(e)))
        
        thread = threading.Thread(target=do_update)
        thread.daemon = True
        thread.start()
    
    def _generate_issue_report(self, report: dict, base_name: str, timestamp: str, output_dir) -> bool:
        """
        生成问题汇总报告
        
        Args:
            report: 清洗报告字典
            base_name: 原始文件名
            timestamp: 时间戳
            output_dir: 输出目录
            
        Returns:
            是否存在问题
        """
        unmatched = report.get('unmatched', {})
        
        # 检查是否有任何问题
        has_column_issues = len(unmatched.get('column_names', [])) > 0
        has_chinese_issues = len(unmatched.get('chinese_meanings', [])) > 0
        has_exchange_issues = len(unmatched.get('exchange_rates', [])) > 0
        has_performance_issues = len(unmatched.get('performance_dimensions', [])) > 0
        has_sku_issues = len(unmatched.get('product_skus', [])) > 0
        
        has_issues = has_column_issues or has_chinese_issues or has_exchange_issues or has_performance_issues
        # 只有SKU未匹配不算异常（用户可能主观不维护SKU映射）
        has_sku_only = has_sku_issues and not has_issues
        has_issues = has_issues or has_sku_issues
        
        # 无论是否有问题都生成报告
        if not has_issues:
            self.log("✅ 所有映射正常，完全清洗成功")
        elif has_sku_only:
            self.log("ℹ️ 仅有SKU未匹配，详情见报告（SKU映射可按需维护）")
        else:
            self.log("⚠️ 发现未匹配项，已生成报告")
        
        # 生成报告文件
        report_file = output_dir / f"清洗问题报告_{base_name}_{timestamp}.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("亚马逊账单清洗问题报告\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"文件: {base_name}.csv\n")
            f.write(f"清洗时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            if not has_issues:
                f.write("状态: 🎉 恭喜你，完全清洗成功！\n\n")
            elif has_sku_only:
                f.write("状态: ℹ️ 商品匹配异常，请维护商品映射表，生成报表已可用\n\n")
            else:
                f.write("状态: ⚠️ 发现异常\n\n")
            
            # 一、未翻译的列名
            if has_column_issues:
                f.write("=" * 60 + "\n")
                f.write("一、未翻译的列名\n")
                f.write("=" * 60 + "\n")
                f.write("[需维护 column_name_full_mapping.csv]\n\n")
                f.write("格式: 原始列名,中文列名\n")
                f.write("示例: Transaction Status,交易状态\n\n")
                for col in unmatched['column_names']:
                    # 截断过长的列名
                    col_display = col[:80] + "..." if len(col) > 80 else col
                    f.write(f"- {col_display}\n")
                f.write("\n")
            
            # 二、未匹配的中文意思
            if has_chinese_issues:
                f.write("=" * 60 + "\n")
                f.write("二、未匹配的中文意思\n")
                f.write("=" * 60 + "\n")
                f.write("[需维护 matching_helper_to_chinese.csv]\n")
                f.write("格式: 匹配辅助列,中文意思\n")
                f.write("示例: US_Product charges_Commission,产品佣金\n\n")
                f.write("【每种类型只显示一条样例，按出现次数降序排列】\n\n")
                
                # 按出现次数降序排列
                items = unmatched['chinese_meanings']
                if items and isinstance(items[0], dict) and '出现次数' in items[0]:
                    items = sorted(items, key=lambda x: x.get('出现次数', 0), reverse=True)
                
                for item in items:
                    if isinstance(item, dict):
                        helper_key = item.get('匹配辅助列', '')
                        count = item.get('出现次数', 1)
                        source_files = item.get('来源文件', set())
                        source_str = ", ".join(sorted(source_files)) if source_files else f"{base_name}.csv"
                        # 显示一行格式：类型名 (出现 X 次)
                        display_key = helper_key if len(helper_key) <= 40 else helper_key[:40] + "..."
                        f.write(f"- {display_key} (出现 {count} 次)\n  📄 来源: {source_str}\n")
                        # 只显示匹配辅助列和样例详情
                        for k, v in item.items():
                            if k not in ('匹配辅助列', '出现次数', '来源文件') and v:
                                f.write(f"  {k}: {v}\n")
                        f.write("\n")
                    else:
                        f.write(f"- {item}\n  📄 来源: {base_name}.csv\n")
                f.write("\n")
            
            # 三、未匹配的绩效维度
            if has_performance_issues:
                f.write("=" * 60 + "\n")
                f.write("三、未匹配的绩效维度\n")
                f.write("=" * 60 + "\n")
                f.write("[需维护 performance_dimension_mapping.csv]\n")
                f.write("格式: 站点,二维匹配列-1,二维匹配列-2,中文意思,账单字段序列,维度,绩效表对应维度\n")
                f.write("示例: US,优惠活动报名费,佣金,优惠活动报名费,33,推广费,推广费\n\n")
                f.write("【每种类型只显示一条样例，按出现次数降序排列】\n\n")
                
                # 按出现次数降序排列
                items = unmatched['performance_dimensions']
                if items and isinstance(items[0], dict) and '出现次数' in items[0]:
                    items = sorted(items, key=lambda x: x.get('出现次数', 0), reverse=True)
                
                for item in items:
                    if isinstance(item, dict):
                        perf_key = item.get('匹配key', '')
                        count = item.get('出现次数', 1)
                        source_files = item.get('来源文件', set())
                        source_str = ", ".join(sorted(source_files)) if source_files else f"{base_name}.csv"
                        # 显示一行格式：匹配key (出现 X 次)
                        f.write(f"- {perf_key} (出现 {count} 次)\n  📄 来源: {source_str}\n")
                        # 只显示样例详情（排除匹配key和出现次数）
                        for k, v in item.items():
                            if k not in ('匹配key', '出现次数', '来源文件') and v:
                                f.write(f"  {k}: {v}\n")
                        f.write("\n")
                    else:
                        f.write(f"- {item}\n  📄 来源: {base_name}.csv\n")
                f.write("\n")
            
            # 四、未匹配的商品SKU
            if has_sku_issues:
                f.write("=" * 60 + "\n")
                f.write("四、未匹配的商品SKU\n")
                f.write("=" * 60 + "\n")
                f.write("[需维护 product_mapping.csv]\n\n")
                f.write("格式: SKU,商品名称,成本(USD),备注\n")
                f.write("示例: B08ABC123,iPhone手机壳,2.50,爆款商品\n\n")
                for sku in unmatched['product_skus']:
                    f.write(f"- {sku}\n  📄 来源: {base_name}.csv\n")
                f.write("\n")
            
            # 五、未匹配的汇率
            if has_exchange_issues:
                f.write("=" * 60 + "\n")
                f.write("五、未匹配的汇率\n")
                f.write("=" * 60 + "\n")
                f.write("[需维护 exchange_rates.csv]\n\n")
                f.write("格式: 币种,汇率,更新日期\n")
                f.write("示例: EUR,1.08,2026-04-21\n\n")
                for item in unmatched['exchange_rates']:
                    f.write(f"- {item}\n  📄 来源: {base_name}.csv\n")
                f.write("\n")
            
            # 维护指南
            f.write("=" * 60 + "\n")
            f.write("维护指南\n")
            f.write("=" * 60 + "\n\n")
            f.write("1. 列名翻译 → 更新 GitHub: bill-cleaner-config/column_name_full_mapping.csv\n")
            f.write("2. 中文意思 → 更新 GitHub: bill-cleaner-config/chinese_meaning_mapping.csv\n")
            f.write("3. 绩效维度 → 更新 GitHub: bill-cleaner-config/performance_dimension_mapping.csv\n")
            f.write("4. 商品SKU → 更新 GitHub: bill-cleaner-config/product_mapping.csv\n")
            f.write("5. 汇率表 → 更新 GitHub: bill-cleaner-config/exchange_rates.csv\n\n")
            f.write("程序启动时会自动拉取最新配置。\n")
        
        if not has_issues:
            self.log(f"✅ 清洗报告已生成: {report_file.name}")
            return False  # 全部正常
        elif has_sku_only:
            self.log(f"ℹ️ SKU未匹配报告已生成: {report_file.name}")
            return 'sku_only'  # 只有SKU问题
        else:
            self.log(f"⚠️ 发现未匹配项，已生成报告: {report_file.name}")
            return True  # 有严重异常
    
    def logout(self):
        """退出登录"""
        if messagebox.askyesno("确认", "确定要退出登录吗？"):
            self.master.destroy()
            self.login_window.deiconify()  # 显示登录窗口
    
    def _create_report_generator_tab(self, parent):
        """创建生成报表选项卡"""
        # 顶部筛选栏
        filter_frame = ttk.LabelFrame(parent, text="筛选条件", padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 第一行筛选条件
        row1_frame = ttk.Frame(filter_frame)
        row1_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(row1_frame, text="结算周期:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.gen_period_var = tk.StringVar()
        self.gen_period_combo = ttk.Combobox(row1_frame, textvariable=self.gen_period_var, 
                                              width=12, state='readonly')
        self.gen_period_combo.pack(side=tk.LEFT, padx=(5, 20))
        
        ttk.Label(row1_frame, text="站点:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.gen_site_var = tk.StringVar()
        self.gen_site_combo = ttk.Combobox(row1_frame, textvariable=self.gen_site_var, 
                                            width=10, state='readonly')
        self.gen_site_combo.pack(side=tk.LEFT, padx=(5, 20))
        
        ttk.Label(row1_frame, text="店铺:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.gen_shop_var = tk.StringVar()
        self.gen_shop_combo = ttk.Combobox(row1_frame, textvariable=self.gen_shop_var, 
                                           width=15, state='readonly')
        self.gen_shop_combo.pack(side=tk.LEFT, padx=(5, 20))
        
        # 第二行按钮
        row2_frame = ttk.Frame(filter_frame)
        row2_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(row2_frame, text="查询数据", command=self._query_financial_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(row2_frame, text="导出Excel", command=self._export_financial_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(row2_frame, text="刷新选项", command=self._refresh_generator_options).pack(side=tk.LEFT, padx=5)
        
        # 提示标签
        ttk.Label(row2_frame, text="提示：筛选条件为空时将汇总所有数据", 
                  font=("Microsoft YaHei", 8), foreground="gray").pack(side=tk.LEFT, padx=20)
        
        # 报表预览区域
        preview_frame = ttk.LabelFrame(parent, text="报表预览", padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建Treeview显示报表
        tree_frame = ttk.Frame(preview_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # 定义报表列名
        report_columns = [
            '结算周期', '站点', '店铺', '订单金额', '平台退款', '退款比例', '订单净额', '销售占比',
            '商品成本', '头程成本', '商品毛利率（含物流成本）', '总成本', '毛利', '毛利率',
            '平台佣金', '推广费', '广告费', '仓储费', '尾程派送费', '平台退/退货手续费/变更费',
            '售后费用', '税费', '索赔', '店铺费用合计', '店铺利润', '店铺利润率'
        ]
        
        self.gen_tree = ttk.Treeview(tree_frame, columns=report_columns, show='headings', height=15)
        
        # 设置列宽和对齐
        for col in report_columns:
            self.gen_tree.heading(col, text=col)
            if col in ['结算周期', '站点', '店铺']:
                self.gen_tree.column(col, width=80, anchor='center')
            elif col in ['退款比例', '毛利率', '店铺利润率', '销售占比', '商品毛利率（含物流成本）']:
                self.gen_tree.column(col, width=120, anchor='center')
            else:
                self.gen_tree.column(col, width=100, anchor='e')
        
        # 垂直滚动条
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.gen_tree.yview)
        self.gen_tree.configure(yscrollcommand=v_scrollbar.set)
        
        # 横向滚动条
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.gen_tree.xview)
        self.gen_tree.configure(xscrollcommand=h_scrollbar.set)
        
        self.gen_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 汇总行
        summary_frame = ttk.LabelFrame(parent, text="汇总统计", padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.gen_summary_labels = {}
        summary_items = [
            ('订单总额', '订单金额'),
            ('退款总额', '平台退款'),
            ('毛利总额', '毛利'),
            ('店铺利润总额', '店铺利润')
        ]
        
        for i, (name, key) in enumerate(summary_items):
            frame = ttk.Frame(summary_frame)
            frame.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=10)
            
            ttk.Label(frame, text=name, font=("Microsoft YaHei", 9)).pack()
            label = ttk.Label(frame, text="0.00", font=("Microsoft YaHei", 12, "bold"))
            label.pack()
            self.gen_summary_labels[key] = label
        
        # 初始化数据库管理器
        from core.db_manager import DatabaseManager
        if not hasattr(self, 'db'):
            self.db = DatabaseManager(USER_DATA_DIR / "amazon_bills.db")
        
        # 刷新选项
        self._refresh_generator_options()
    
    def _refresh_generator_options(self):
        """刷新生成报表选项"""
        # 获取结算周期列表
        periods = self.db.get_all_periods()
        self.gen_period_combo['values'] = ['(全部)'] + periods
        
        # 获取站点列表
        sites = self.db.get_all_sites()
        self.gen_site_combo['values'] = ['(全部)'] + sites
        
        # 获取店铺列表
        shops = self.db.get_all_shops()
        self.gen_shop_combo['values'] = ['(全部)'] + shops
        
        # 默认选择全部
        if self.gen_period_combo['values']:
            self.gen_period_combo.set('(全部)')
        if self.gen_site_combo['values']:
            self.gen_site_combo.set('(全部)')
        if self.gen_shop_combo['values']:
            self.gen_shop_combo.set('(全部)')
    
    def _query_financial_report(self):
        """查询财务报表"""
        import pandas as pd
        
        # 获取筛选条件
        period = self.gen_period_var.get()
        site = self.gen_site_var.get()
        shop = self.gen_shop_var.get()
        
        # 处理"全部"选项
        period = None if period == '(全部)' or not period else period
        site = None if site == '(全部)' or not site else site
        shop = None if shop == '(全部)' or not shop else shop
        
        # 生成报表
        try:
            df = self.db.generate_financial_report(
                settlement_period=period,
                site=site,
                shop_name=shop
            )
            
            if df.empty:
                messagebox.showinfo("提示", "未找到符合条件的数据")
                return
            
            # 清空现有数据
            for item in self.gen_tree.get_children():
                self.gen_tree.delete(item)
            
            # 定义显示列（完整27列）
            display_columns = [
                '结算周期', '站点', '店铺', '订单金额', '平台退款', '退款比例', '订单净额', '销售占比',
                '商品成本', '头程成本', '商品毛利率（含物流成本）', '总成本', '毛利', '毛利率',
                '平台佣金', '推广费', '广告费', '仓储费', '尾程派送费', '平台退/退货手续费/变更费',
                '售后费用', '税费', '索赔', '店铺费用合计', '店铺利润', '店铺利润率'
            ]
            
            # 百分比列
            percent_cols = ['退款比例', '毛利率', '店铺利润率', '销售占比', '商品毛利率（含物流成本）']
            # 金额列
            money_cols = ['订单金额', '平台退款', '订单净额', '商品成本', '头程成本', '总成本',
                         '毛利', '平台佣金', '推广费', '广告费', '仓储费', '尾程派送费',
                         '平台退/退货手续费/变更费', '售后费用', '税费', '索赔', '店铺费用合计', '店铺利润']
            
            # 插入数据
            for _, row in df.iterrows():
                values = []
                for col in display_columns:
                    val = row.get(col, 0)
                    if col in percent_cols:
                        values.append(f"{val:.2%}" if pd.notna(val) else "0.00%")
                    elif col in money_cols:
                        values.append(f"{val:,.2f}" if pd.notna(val) else "0.00")
                    else:
                        values.append(val if pd.notna(val) else '')
                
                self.gen_tree.insert('', 'end', values=values)
            
            # 更新汇总
            total_order = df['订单金额'].sum()
            total_refund = df['平台退款'].sum()
            total_profit = df['毛利'].sum()
            total_shop_profit = df['店铺利润'].sum()
            
            self.gen_summary_labels['订单金额'].config(text=f"{total_order:,.2f}")
            self.gen_summary_labels['平台退款'].config(text=f"{total_refund:,.2f}")
            self.gen_summary_labels['毛利'].config(text=f"{total_profit:,.2f}")
            self.gen_summary_labels['店铺利润'].config(text=f"{total_shop_profit:,.2f}")
            
            # 保存完整报表数据用于导出
            self._current_report_df = df
            
            messagebox.showinfo("成功", f"查询完成，共 {len(df)} 条记录")
            
        except Exception as e:
            messagebox.showerror("错误", f"查询失败: {e}")
    
    def _export_financial_report(self):
        """导出财务报表为Excel"""
        if not hasattr(self, '_current_report_df') or self._current_report_df is None or self._current_report_df.empty:
            messagebox.showwarning("提示", "请先查询数据后再导出")
            return
        
        import pandas as pd
        
        try:
            # 选择保存路径
            file_path = filedialog.asksaveasfilename(
                title="保存报表",
                defaultextension=".xlsx",
                filetypes=[("Excel文件", "*.xlsx")],
                initialdir=str(OUTPUT_DIR),
                initialfile=f"财务报表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            
            if not file_path:
                return
            
            # 导出到Excel
            df = self._current_report_df.copy()
            
            # 格式化百分比列
            if '退款比例' in df.columns:
                df['退款比例'] = df['退款比例'].apply(lambda x: f"{x:.2%}")
            if '毛利率' in df.columns:
                df['毛利率'] = df['毛利率'].apply(lambda x: f"{x:.2%}")
            if '店铺利润率' in df.columns:
                df['店铺利润率'] = df['店铺利润率'].apply(lambda x: f"{x:.2%}")
            if '销售占比' in df.columns:
                df['销售占比'] = df['销售占比'].apply(lambda x: f"{x:.2%}")
            if '商品毛利率（含物流成本）' in df.columns:
                df['商品毛利率（含物流成本）'] = df['商品毛利率（含物流成本）'].apply(lambda x: f"{x:.2%}")
            
            # 格式化金额列
            money_columns = ['订单金额', '平台退款', '订单净额', '商品成本', '头程成本', '总成本', 
                           '毛利', '平台佣金', '推广费', '广告费', '仓储费', '尾程派送费',
                           '平台退/退货手续费/变更费', '售后费用', '税费', '索赔', '店铺费用合计', 
                           '店铺利润']
            
            for col in money_columns:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: round(x, 2) if pd.notna(x) else 0)
            
            # 使用pandas导出
            df.to_excel(file_path, index=False, sheet_name='财务报表')
            
            messagebox.showinfo("成功", f"报表已导出到:\n{file_path}")
            
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")
    
    def _create_voucher_tab(self, parent):
        """创建财务凭证选项卡"""
        # 顶部筛选栏
        filter_frame = ttk.LabelFrame(parent, text="筛选条件", padding=10)
        filter_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 第一行筛选条件
        row1_frame = ttk.Frame(filter_frame)
        row1_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(row1_frame, text="结算周期:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.voucher_period_var = tk.StringVar()
        self.voucher_period_combo = ttk.Combobox(row1_frame, textvariable=self.voucher_period_var, 
                                                  width=12, state='readonly')
        self.voucher_period_combo.pack(side=tk.LEFT, padx=(5, 20))
        
        ttk.Label(row1_frame, text="站点:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.voucher_site_var = tk.StringVar()
        self.voucher_site_combo = ttk.Combobox(row1_frame, textvariable=self.voucher_site_var, 
                                                width=10, state='readonly')
        self.voucher_site_combo.pack(side=tk.LEFT, padx=(5, 20))
        
        ttk.Label(row1_frame, text="店铺:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.voucher_shop_var = tk.StringVar()
        self.voucher_shop_combo = ttk.Combobox(row1_frame, textvariable=self.voucher_shop_var, 
                                               width=15, state='readonly')
        self.voucher_shop_combo.pack(side=tk.LEFT, padx=(5, 20))
        
        # 第二行按钮
        row2_frame = ttk.Frame(filter_frame)
        row2_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(row2_frame, text="查询凭证", command=self._query_voucher).pack(side=tk.LEFT, padx=5)
        ttk.Button(row2_frame, text="导出Excel", command=self._export_voucher).pack(side=tk.LEFT, padx=5)
        ttk.Button(row2_frame, text="刷新选项", command=self._refresh_voucher_options).pack(side=tk.LEFT, padx=5)
        
        # 提示标签
        ttk.Label(row2_frame, text="提示：筛选条件为空时将汇总所有数据", 
                  font=("Microsoft YaHei", 8), foreground="gray").pack(side=tk.LEFT, padx=20)
        
        # 顶部汇总栏
        summary_frame = ttk.LabelFrame(parent, text="亚马逊0店0月做账凭证", padding=10)
        summary_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 汇总信息行
        summary_row = ttk.Frame(summary_frame)
        summary_row.pack(fill=tk.X)
        
        # 左半边：站点、店铺、结算月份
        left_summary = ttk.Frame(summary_row)
        left_summary.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(left_summary, text="站点:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.voucher_site_label = ttk.Label(left_summary, text="0", font=("Microsoft YaHei", 9, "bold"))
        self.voucher_site_label.pack(side=tk.LEFT, padx=(5, 20))
        
        ttk.Label(left_summary, text="店铺:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.voucher_shop_label = ttk.Label(left_summary, text="0", font=("Microsoft YaHei", 9, "bold"))
        self.voucher_shop_label.pack(side=tk.LEFT, padx=(5, 20))
        
        ttk.Label(left_summary, text="结算月份:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.voucher_month_label = ttk.Label(left_summary, text="1900/1/0", font=("Microsoft YaHei", 9, "bold"))
        self.voucher_month_label.pack(side=tk.LEFT, padx=(5, 20))
        
        # 右半边：校验、已结算、未结算
        right_summary = ttk.Frame(summary_row)
        right_summary.pack(side=tk.RIGHT, fill=tk.X, expand=True)
        
        # 已结算区域
        settled_frame = ttk.Frame(right_summary)
        settled_frame.pack(side=tk.LEFT, padx=10)
        
        ttk.Label(settled_frame, text="校验:", font=("Microsoft YaHei", 9), foreground="red").pack(side=tk.LEFT)
        ttk.Label(settled_frame, text="已结算原币:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(10, 0))
        self.voucher_settled_orig_label = ttk.Label(settled_frame, text="0.00", font=("Microsoft YaHei", 9, "bold"))
        self.voucher_settled_orig_label.pack(side=tk.LEFT, padx=(5, 10))
        
        ttk.Label(settled_frame, text="已结算本币:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.voucher_settled_usd_label = ttk.Label(settled_frame, text="0.00", font=("Microsoft YaHei", 9, "bold"))
        self.voucher_settled_usd_label.pack(side=tk.LEFT, padx=(5, 10))
        
        # 未结算区域
        unsettled_frame = ttk.Frame(right_summary)
        unsettled_frame.pack(side=tk.LEFT, padx=10)
        
        ttk.Label(settled_frame, text="校验:", font=("Microsoft YaHei", 9), foreground="red").pack(side=tk.LEFT)
        ttk.Label(unsettled_frame, text="未结算原币:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=(10, 0))
        self.voucher_unsettled_orig_label = ttk.Label(unsettled_frame, text="0.00", font=("Microsoft YaHei", 9, "bold"))
        self.voucher_unsettled_orig_label.pack(side=tk.LEFT, padx=(5, 10))
        
        ttk.Label(unsettled_frame, text="未结算本币:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.voucher_unsettled_usd_label = ttk.Label(unsettled_frame, text="0.00", font=("Microsoft YaHei", 9, "bold"))
        self.voucher_unsettled_usd_label.pack(side=tk.LEFT, padx=(5, 10))
        
        # 凭证明细区域 - 使用Canvas实现滚动
        detail_frame = ttk.LabelFrame(parent, text="凭证明细", padding=10)
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建Canvas和滚动条
        self.voucher_canvas = tk.Canvas(detail_frame, bg='white')
        voucher_scrollbar_y = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL, command=self.voucher_canvas.yview)
        voucher_scrollbar_x = ttk.Scrollbar(detail_frame, orient=tk.HORIZONTAL, command=self.voucher_canvas.xview)
        self.voucher_canvas.configure(yscrollcommand=voucher_scrollbar_y.set, xscrollcommand=voucher_scrollbar_x.set)
        
        voucher_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        voucher_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.voucher_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 创建内部Frame用于放置凭证明细
        self.voucher_inner_frame = ttk.Frame(self.voucher_canvas)
        self.voucher_canvas.create_window((0, 0), window=self.voucher_inner_frame, anchor='nw')
        
        # 绑定配置函数
        def configure_voucher_scroll(event):
            self.voucher_canvas.configure(scrollregion=self.voucher_canvas.bbox('all'))
        
        self.voucher_inner_frame.bind('<Configure>', configure_voucher_scroll)
        
        # 凭证分类标题和Treeview字典
        self.voucher_trees = {}
        self.voucher_category_frames = {}
        
        # 凭证分类标题（红色字体）
        voucher_categories = [
            (1, '①收入确认凭证'),
            (2, '②费用支出凭证'),
            (3, '③税费凭证'),
            (4, '④提现凭证')
        ]
        
        # 已结算凭证区域
        settled_label_frame = ttk.LabelFrame(self.voucher_inner_frame, text="已结算凭证", padding=5)
        settled_label_frame.pack(fill=tk.X, pady=5)
        
        for cat_id, title in voucher_categories:
            # 红色标题
            cat_frame = ttk.Frame(settled_label_frame)
            cat_frame.pack(fill=tk.X, pady=2)
            
            title_label = tk.Label(cat_frame, text=title, font=("Microsoft YaHei", 10, "bold"), 
                                   fg="red", bg='white')
            title_label.pack(side=tk.LEFT, anchor='w')
            
            # 明细表格
            tree_frame = ttk.Frame(cat_frame)
            tree_frame.pack(fill=tk.X, pady=2)
            
            columns = ('direction', 'account', 'settled_original', 'settled_usd', 'unsettled_original', 'unsettled_usd')
            tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=4)
            
            tree.heading('direction', text='科目方向')
            tree.heading('account', text='建议科目')
            tree.heading('settled_original', text='已结算原币/本币(USD)')
            tree.heading('settled_usd', text='已结算本币')
            tree.heading('unsettled_original', text='未结算原币')
            tree.heading('unsettled_usd', text='未结算本币')
            
            tree.column('direction', width=80, anchor='center')
            tree.column('account', width=200)
            tree.column('settled_original', width=150, anchor='e')
            tree.column('settled_usd', width=120, anchor='e')
            tree.column('unsettled_original', width=120, anchor='e')
            tree.column('unsettled_usd', width=120, anchor='e')
            
            # 隐藏不需要显示的列
            tree['displaycolumns'] = ('direction', 'account', 'settled_original', 'unsettled_original')
            
            scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            self.voucher_trees[cat_id] = {'settled': tree, 'unsettled': None}
        
        # 未结算凭证区域
        unsettled_label_frame = ttk.LabelFrame(self.voucher_inner_frame, text="未结算凭证", padding=5)
        unsettled_label_frame.pack(fill=tk.X, pady=5)
        
        for cat_id, title in voucher_categories:
            # 红色标题
            cat_frame = ttk.Frame(unsettled_label_frame)
            cat_frame.pack(fill=tk.X, pady=2)
            
            title_label = tk.Label(cat_frame, text=title, font=("Microsoft YaHei", 10, "bold"), 
                                   fg="red", bg='white')
            title_label.pack(side=tk.LEFT, anchor='w')
            
            # 明细表格
            tree_frame = ttk.Frame(cat_frame)
            tree_frame.pack(fill=tk.X, pady=2)
            
            columns = ('direction', 'account', 'settled_original', 'settled_usd', 'unsettled_original', 'unsettled_usd')
            tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=4)
            
            tree.heading('direction', text='科目方向')
            tree.heading('account', text='建议科目')
            tree.heading('settled_original', text='已结算原币')
            tree.heading('settled_usd', text='已结算本币')
            tree.heading('unsettled_original', text='未结算原币/本币(USD)')
            tree.heading('unsettled_usd', text='未结算本币')
            
            tree.column('direction', width=80, anchor='center')
            tree.column('account', width=200)
            tree.column('settled_original', width=120, anchor='e')
            tree.column('settled_usd', width=120, anchor='e')
            tree.column('unsettled_original', width=150, anchor='e')
            tree.column('unsettled_usd', width=120, anchor='e')
            
            # 显示未结算列
            tree['displaycolumns'] = ('direction', 'account', 'unsettled_original')
            
            scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            self.voucher_trees[cat_id]['unsettled'] = tree
        
        # 初始化数据库管理器
        from core.db_manager import DatabaseManager
        if not hasattr(self, 'db'):
            self.db = DatabaseManager(USER_DATA_DIR / "amazon_bills.db")
        
        # 刷新选项
        self._refresh_voucher_options()
    
    def _refresh_voucher_options(self):
        """刷新财务凭证选项"""
        # 获取结算周期列表
        periods = self.db.get_all_periods()
        self.voucher_period_combo['values'] = ['(全部)'] + periods
        
        # 获取站点列表
        sites = self.db.get_all_sites()
        self.voucher_site_combo['values'] = ['(全部)'] + sites
        
        # 获取店铺列表
        shops = self.db.get_all_shops()
        self.voucher_shop_combo['values'] = ['(全部)'] + shops
        
        # 默认选择全部
        if self.voucher_period_combo['values']:
            self.voucher_period_combo.set('(全部)')
        if self.voucher_site_combo['values']:
            self.voucher_site_combo.set('(全部)')
        if self.voucher_shop_combo['values']:
            self.voucher_shop_combo.set('(全部)')
    
    def _query_voucher(self):
        """查询财务凭证"""
        # 获取筛选条件
        period = self.voucher_period_var.get()
        site = self.voucher_site_var.get()
        shop = self.voucher_shop_var.get()
        
        # 处理"全部"选项
        period = None if period == '(全部)' or not period else period
        site = None if site == '(全部)' or not site else site
        shop = None if shop == '(全部)' or not shop else shop
        
        # 获取凭证数据
        try:
            voucher_data = self.db.get_voucher_data(
                settlement_period=period,
                site=site,
                shop_name=shop
            )
            
            if not voucher_data:
                messagebox.showinfo("提示", "未找到符合条件的数据")
                return
            
            # 更新顶部汇总
            summary = voucher_data['summary']
            self.voucher_site_label.config(text=summary.get('site', '0'))
            self.voucher_shop_label.config(text=summary.get('shop_name', '0') or '0')
            self.voucher_month_label.config(text=summary.get('settlement_month', '1900/1/0'))
            self.voucher_settled_orig_label.config(text=f"{summary.get('settled_original', 0):,.2f}")
            self.voucher_settled_usd_label.config(text=f"{summary.get('settled_usd', 0):,.2f}")
            self.voucher_unsettled_orig_label.config(text=f"{summary.get('unsettled_original', 0):,.2f}")
            self.voucher_unsettled_usd_label.config(text=f"{summary.get('unsettled_usd', 0):,.2f}")
            
            # 清空所有表格
            for cat_id in [1, 2, 3, 4]:
                for tree_type in ['settled', 'unsettled']:
                    tree = self.voucher_trees[cat_id][tree_type]
                    if tree:
                        for item in tree.get_children():
                            tree.delete(item)
            
            # 填充已结算凭证明细
            settled_vouchers = voucher_data.get('settled_vouchers', {})
            for cat_id, items in settled_vouchers.items():
                tree = self.voucher_trees[cat_id]['settled']
                if tree:
                    # 先添加借方汇总行（应收账款）
                    if cat_id == 1:  # 收入确认凭证
                        total_settled = summary.get('settled_original', 0)
                        if total_settled > 0:
                            tree.insert('', 'end', values=(
                                '借',
                                '应收账款-X店铺',
                                f"{total_settled:,.2f}",
                                '0.00'
                            ), tags=('total',))
                    
                    # 添加各科目行
                    total_cat_settled = 0
                    for item in items:
                        amount_str = f"{item['original']:,.2f}"
                        usd_str = f"{item['usd']:,.2f}"
                        tree.insert('', 'end', values=(
                            item['direction'],
                            item['account'],
                            amount_str,
                            usd_str
                        ))
                        total_cat_settled += item['original']
                    
                    # 添加合计行
                    tree.insert('', 'end', values=(
                        '合计',
                        '',
                        f"{total_cat_settled:,.2f}",
                        f"{total_cat_settled:,.2f}"
                    ), tags=('total',))
            
            # 填充未结算凭证明细
            unsettled_vouchers = voucher_data.get('unsettled_vouchers', {})
            for cat_id, items in unsettled_vouchers.items():
                tree = self.voucher_trees[cat_id]['unsettled']
                if tree:
                    # 先添加借方汇总行（应收账款）
                    if cat_id == 1:  # 收入确认凭证
                        total_unsettled = summary.get('unsettled_original', 0)
                        if total_unsettled > 0:
                            tree.insert('', 'end', values=(
                                '借',
                                '应收账款-X店铺',
                                '0.00',
                                f"{total_unsettled:,.2f}"
                            ), tags=('total',))
                    
                    # 添加各科目行
                    total_cat_unsettled = 0
                    for item in items:
                        amount_str = f"{item['original']:,.2f}"
                        usd_str = f"{item['usd']:,.2f}"
                        tree.insert('', 'end', values=(
                            item['direction'],
                            item['account'],
                            '0.00',
                            amount_str
                        ))
                        total_cat_unsettled += item['original']
                    
                    # 添加合计行
                    if total_cat_unsettled > 0:
                        tree.insert('', 'end', values=(
                            '合计',
                            '',
                            '0.00',
                            f"{total_cat_unsettled:,.2f}"
                        ), tags=('total',))
            
            # 配置合计行样式
            for cat_id in [1, 2, 3, 4]:
                for tree_type in ['settled', 'unsettled']:
                    tree = self.voucher_trees[cat_id][tree_type]
                    if tree:
                        tree.tag_configure('total', foreground='blue', font=("Microsoft YaHei", 9, "bold"))
            
            # 存储凭证数据供导出使用
            self._current_voucher_data = voucher_data
            
        except Exception as e:
            messagebox.showerror("错误", f"查询失败: {e}")
    
    def _export_voucher(self):
        """导出财务凭证到Excel"""
        if not hasattr(self, '_current_voucher_data') or not self._current_voucher_data:
            messagebox.showwarning("提示", "请先查询凭证数据")
            return
        
        try:
            import pandas as pd
            
            # 选择导出路径
            file_path = filedialog.asksaveasfilename(
                title="导出财务凭证",
                defaultextension=".xlsx",
                filetypes=[("Excel文件", "*.xlsx")],
                initialdir=str(OUTPUT_DIR),
                initialfile=f"财务凭证_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            
            if not file_path:
                return
            
            voucher_data = self._current_voucher_data
            summary = voucher_data['summary']
            
            # 创建Excel writer
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                # Sheet 1: 汇总信息
                summary_data = {
                    '项目': ['站点', '店铺', '结算月份', '已结算原币', '已结算本币(USD)', '未结算原币', '未结算本币(USD)'],
                    '值': [
                        summary.get('site', ''),
                        summary.get('shop_name', ''),
                        summary.get('settlement_month', ''),
                        round(summary.get('settled_original', 0), 2),
                        round(summary.get('settled_usd', 0), 2),
                        round(summary.get('unsettled_original', 0), 2),
                        round(summary.get('unsettled_usd', 0), 2)
                    ]
                }
                pd.DataFrame(summary_data).to_excel(writer, sheet_name='汇总', index=False)
                
                # Sheet 2: 已结算凭证
                settled_rows = []
                settled_vouchers = voucher_data.get('settled_vouchers', {})
                category_titles = {1: '①收入确认凭证', 2: '②费用支出凭证', 3: '③税费凭证', 4: '④提现凭证'}
                
                for cat_id in [1, 2, 3, 4]:
                    items = settled_vouchers.get(cat_id, [])
                    if items:
                        settled_rows.append([category_titles[cat_id], '', '', '', ''])
                        settled_rows.append(['科目方向', '建议科目', '已结算原币', '已结算本币(USD)', ''])
                        for item in items:
                            settled_rows.append([
                                item['direction'],
                                item['account'],
                                round(item['original'], 2),
                                round(item['usd'], 2),
                                ''
                            ])
                
                if settled_rows:
                    pd.DataFrame(settled_rows).to_excel(writer, sheet_name='已结算凭证', index=False, header=False)
                
                # Sheet 3: 未结算凭证
                unsettled_rows = []
                unsettled_vouchers = voucher_data.get('unsettled_vouchers', {})
                
                for cat_id in [1, 2, 3, 4]:
                    items = unsettled_vouchers.get(cat_id, [])
                    if items:
                        unsettled_rows.append([category_titles[cat_id], '', '', '', ''])
                        unsettled_rows.append(['科目方向', '建议科目', '未结算原币', '未结算本币(USD)', ''])
                        for item in items:
                            unsettled_rows.append([
                                item['direction'],
                                item['account'],
                                round(item['original'], 2),
                                round(item['usd'], 2),
                                ''
                            ])
                
                if unsettled_rows:
                    pd.DataFrame(unsettled_rows).to_excel(writer, sheet_name='未结算凭证', index=False, header=False)
            
            messagebox.showinfo("成功", f"凭证已导出到:\n{file_path}")
            
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {e}")


class ProductMappingWindow:
    """商品映射表维护窗口"""
    
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("商品映射表维护")
        self.window.geometry("500x400")
        self.window.transient(parent)
        self.window.grab_set()
        
        self.create_widgets()
        self.load_info()
    
    def create_widgets(self):
        """创建界面"""
        # 信息显示
        info_frame = ttk.LabelFrame(self.window, text="当前映射表信息", padding=10)
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.info_label = ttk.Label(info_frame, text="加载中...")
        self.info_label.pack(anchor=tk.W)
        
        self.data_dir_label = ttk.Label(info_frame, text=f"数据目录: {USER_MAPPINGS_DIR}",
                                         font=("Microsoft YaHei", 8), foreground="gray")
        self.data_dir_label.pack(anchor=tk.W, pady=(5, 0))
        
        # 操作按钮
        btn_frame = ttk.Frame(self.window, padding=10)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="上传映射表", width=15, 
                   command=self.upload_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="查看详情", width=15, 
                   command=self.view_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="清空映射表", width=15, 
                   command=self.clear_mapping).pack(side=tk.LEFT, padx=5)
        
        # 说明
        help_frame = ttk.LabelFrame(self.window, text="说明", padding=10)
        help_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        help_text = """
支持格式：CSV、XLSX

必需列名：SELLERSKU（用于匹配账单SKU）

可选列名：
  - ASIN
  - FNSKU  
  - 产品ID
  - 一级大类、二级类目、三级类目
  - 最新采购价

商品映射表存储在用户数据目录，
更新程序不会丢失数据。
        """
        ttk.Label(help_frame, text=help_text, font=("Microsoft YaHei", 9), 
                  justify=tk.LEFT).pack(anchor=tk.W)
    
    def load_info(self):
        """加载映射表信息"""
        mapping_file = USER_MAPPINGS_DIR / "product_mapping.csv"
        
        if mapping_file.exists():
            try:
                import pandas as pd
                df = pd.read_csv(mapping_file, encoding='utf-8-sig')
                self.info_label.config(text=f"📄 商品数量: {len(df)} 条")
            except Exception as e:
                self.info_label.config(text=f"⚠️ 读取失败: {e}")
        else:
            self.info_label.config(text="📄 当前无映射表，请上传")
    
    def upload_file(self):
        """上传文件"""
        file_path = filedialog.askopenfilename(
            title="选择商品映射表",
            filetypes=[("CSV文件", "*.csv"), ("Excel文件", "*.xlsx"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            import pandas as pd
            import shutil
            
            # 读取文件
            if file_path.endswith('.xlsx'):
                df = pd.read_excel(file_path)
            else:
                df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            # 检查必需列
            if 'SELLERSKU' not in df.columns:
                messagebox.showerror("错误", "文件缺少 SELLERSKU 列！")
                return
            
            # 保存
            USER_MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)
            output_file = USER_MAPPINGS_DIR / "product_mapping.csv"
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            
            self.load_info()
            messagebox.showinfo("成功", f"上传成功！\n商品数量: {len(df)} 条")
            
        except Exception as e:
            messagebox.showerror("错误", f"上传失败: {e}")
    
    def view_details(self):
        """查看详情"""
        mapping_file = USER_MAPPINGS_DIR / "product_mapping.csv"
        
        if not mapping_file.exists():
            messagebox.showwarning("提示", "当前无映射表")
            return
        
        try:
            import pandas as pd
            df = pd.read_csv(mapping_file, encoding='utf-8-sig')
            
            # 显示详情窗口
            detail_window = tk.Toplevel(self.window)
            detail_window.title("映射表详情")
            detail_window.geometry("600x400")
            
            # 创建表格
            frame = ttk.Frame(detail_window)
            frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            tree = ttk.Treeview(frame, columns=list(df.columns), show="headings", height=15)
            
            for col in df.columns:
                tree.heading(col, text=col)
                tree.column(col, width=100)
            
            for _, row in df.head(100).iterrows():
                tree.insert("", tk.END, values=list(row))
            
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
        except Exception as e:
            messagebox.showerror("错误", f"读取失败: {e}")
    
    def clear_mapping(self):
        """清空映射表"""
        if messagebox.askyesno("确认", "确定要清空商品映射表吗？"):
            mapping_file = USER_MAPPINGS_DIR / "product_mapping.csv"
            if mapping_file.exists():
                mapping_file.unlink()
            self.load_info()
            messagebox.showinfo("完成", "已清空")

    def get_all_exchange_rates_with_source(self):
        """获取所有汇率及其来源"""
        from core.bill_cleaner import BillCleaner
        cleaner = BillCleaner(MAPPINGS_DIR, USER_DATA_DIR)
        
        rates = []
        for key, rate in cleaner.exchange_rates.items():
            parts = key.rsplit('_', 1)
            currency = parts[0]
            period = parts[1] if len(parts) > 1 else ''
            source = cleaner.exchange_rate_sources.get(key, 'unknown')
            rates.append({
                'currency': currency,
                'period': period,
                'rate': rate,
                'source': source
            })
        return rates


class ExchangeRateManager:
    """汇率管理弹窗"""
    
    def __init__(self, parent, mappings_dir, user_data_dir):
        self.parent = parent
        self.mappings_dir = mappings_dir
        self.user_data_dir = user_data_dir
        self.local_file = user_data_dir / "local_exchange_rate.csv"
        
        # 加载汇率数据
        self.github_rates = self._load_github_rates()
        self.local_rates = self._load_local_rates()
        
        # 创建弹窗
        self.window = tk.Toplevel(parent)
        self.window.title("汇率管理")
        self.window.geometry("700x500")
        self.window.transient(parent)
        self.window.grab_set()
        
        self.create_widgets()
        self.refresh_tree()
        
        # 居中显示
        self.window.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 700) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 500) // 2
        self.window.geometry(f"700x500+{x}+{y}")
    
    def _load_github_rates(self):
        """加载GitHub基准汇率"""
        rates = {}
        file_path = self.mappings_dir / "汇率表_各币种兑美元.csv"
        if file_path.exists():
            try:
                df = pd.read_csv(file_path, encoding='utf-8-sig')
                for _, row in df.iterrows():
                    key = f"{row['币种']}_{row['结算周期']}"
                    rates[key] = float(row['汇率(原币->USD)'])
            except Exception as e:
                print(f"加载GitHub汇率失败: {e}")
        return rates
    
    def _load_local_rates(self):
        """加载本地覆盖汇率"""
        rates = {}
        if self.local_file.exists():
            try:
                df = pd.read_csv(self.local_file, encoding='utf-8-sig')
                for _, row in df.iterrows():
                    key = f"{row['币种']}_{row['结算周期']}"
                    rates[key] = float(row['汇率(原币->USD)'])
            except Exception as e:
                print(f"加载本地汇率失败: {e}")
        return rates
    
    def _save_local_rates(self):
        """保存本地覆盖汇率到文件"""
        self.local_file.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame([
            {'币种': k.split('_')[0], '汇率(原币->USD)': v, '结算周期': k.split('_')[1]}
            for k, v in self.local_rates.items()
        ])
        df.to_csv(self.local_file, index=False, encoding='utf-8-sig')
    
    def create_widgets(self):
        """创建界面组件"""
        # 顶部筛选区
        filter_frame = ttk.Frame(self.window, padding=10)
        filter_frame.pack(fill=tk.X)
        
        ttk.Label(filter_frame, text="币种筛选:").pack(side=tk.LEFT)
        self.currency_filter = ttk.Combobox(filter_frame, width=10)
        self.currency_filter.pack(side=tk.LEFT, padx=5)
        self.currency_filter.bind('<<ComboboxSelected>>', lambda e: self.refresh_tree())
        self.currency_filter.bind('<KeyRelease>', lambda e: self.refresh_tree())
        
        ttk.Label(filter_frame, text="结算周期:").pack(side=tk.LEFT, padx=(10, 0))
        self.period_filter = ttk.Combobox(filter_frame, width=10)
        self.period_filter.pack(side=tk.LEFT, padx=5)
        self.period_filter.bind('<<ComboboxSelected>>', lambda e: self.refresh_tree())
        
        ttk.Button(filter_frame, text="清除筛选", command=self.clear_filters).pack(side=tk.LEFT, padx=10)
        
        # 仅看本地覆盖
        self.local_only_var = tk.BooleanVar()
        ttk.Checkbutton(filter_frame, text="只看本地覆盖", variable=self.local_only_var,
                        command=self.refresh_tree).pack(side=tk.LEFT, padx=10)
        
        # 汇率表格
        tree_frame = ttk.Frame(self.window, padding=5)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ('币种', '结算周期', '汇率', '来源')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        self.tree.heading('币种', text='币种')
        self.tree.heading('结算周期', text='结算周期')
        self.tree.heading('汇率', text='汇率(原币->USD)')
        self.tree.heading('来源', text='来源')
        
        self.tree.column('币种', width=80, anchor='center')
        self.tree.column('结算周期', width=100, anchor='center')
        self.tree.column('汇率', width=120, anchor='e')
        self.tree.column('来源', width=80, anchor='center')
        
        # 设置来源列的颜色回调
        self.tree.tag_configure('github', foreground='blue')
        self.tree.tag_configure('local', foreground='green')
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 选中事件
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        
        # 添加/修改区
        edit_frame = ttk.LabelFrame(self.window, text="添加/修改本地覆盖汇率", padding=10)
        edit_frame.pack(fill=tk.X, padx=10, pady=5)
        
        input_frame = ttk.Frame(edit_frame)
        input_frame.pack()
        
        ttk.Label(input_frame, text="币种:").pack(side=tk.LEFT)
        self.currency_entry = ttk.Entry(input_frame, width=8)
        self.currency_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(input_frame, text="结算周期:").pack(side=tk.LEFT, padx=(10, 0))
        self.period_entry = ttk.Entry(input_frame, width=8)
        self.period_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(input_frame, text="汇率:").pack(side=tk.LEFT, padx=(10, 0))
        self.rate_entry = ttk.Entry(input_frame, width=12)
        self.rate_entry.pack(side=tk.LEFT, padx=5)
        
        btn_frame = ttk.Frame(edit_frame)
        btn_frame.pack(pady=10)
        
        # 使用tk.Button替代ttk.Button，支持背景色，加大尺寸
        tk.Button(btn_frame, text="➕ 添加/更新", command=self.add_or_update, 
                  bg="#4CAF50", fg="white", font=("Microsoft YaHei", 10, "bold"),
                  width=14, height=1, relief=tk.RAISED, cursor="hand2").pack(side=tk.LEFT, padx=8, pady=5)
        tk.Button(btn_frame, text="🗑️ 删除选中", command=self.delete_selected, 
                  bg="#f44336", fg="white", font=("Microsoft YaHei", 10, "bold"),
                  width=14, height=1, relief=tk.RAISED, cursor="hand2").pack(side=tk.LEFT, padx=8, pady=5)
        tk.Button(btn_frame, text="🔄 刷新", command=self.refresh_tree, 
                  bg="#2196F3", fg="white", font=("Microsoft YaHei", 10, "bold"),
                  width=14, height=1, relief=tk.RAISED, cursor="hand2").pack(side=tk.LEFT, padx=8, pady=5)
        tk.Button(btn_frame, text="✖ 关闭", command=self.window.destroy, 
                  bg="#757575", fg="white", font=("Microsoft YaHei", 10, "bold"),
                  width=14, height=1, relief=tk.RAISED, cursor="hand2").pack(side=tk.LEFT, padx=8, pady=5)
        
        # 状态提示
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(edit_frame, textvariable=self.status_var, foreground="gray").pack()
        
        # 加载筛选选项
        self.load_filter_options()
    
    def load_filter_options(self):
        """加载筛选选项"""
        currencies = set()
        periods = set()
        
        for key in self.github_rates:
            parts = key.rsplit('_', 1)
            if len(parts) == 2:
                currencies.add(parts[0])
                periods.add(parts[1])
        
        for key in self.local_rates:
            parts = key.rsplit('_', 1)
            if len(parts) == 2:
                currencies.add(parts[0])
                periods.add(parts[1])
        
        self.currency_filter['values'] = sorted(currencies)
        self.period_filter['values'] = sorted(periods)
    
    def clear_filters(self):
        """清除筛选"""
        self.currency_filter.set('')
        self.period_filter.set('')
        self.local_only_var.set(False)
        self.refresh_tree()
    
    def refresh_tree(self):
        """刷新表格"""
        # 清空表格
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # 获取筛选条件
        currency_filter = self.currency_filter.get().strip().upper()
        period_filter = self.period_filter.get().strip()
        local_only = self.local_only_var.get()
        
        # 合并汇率（本地优先）
        all_rates = dict(self.github_rates)
        for key, rate in self.local_rates.items():
            all_rates[key] = rate
        
        # 插入数据
        for key, rate in sorted(all_rates.items()):
            parts = key.rsplit('_', 1)
            if len(parts) != 2:
                continue
            
            currency, period = parts
            is_local = key in self.local_rates
            source = '本地' if is_local else '官方'
            
            # 应用筛选
            if local_only and not is_local:
                continue
            if currency_filter and currency.upper() != currency_filter:
                continue
            if period_filter and period != period_filter:
                continue
            
            tag = 'local' if is_local else 'github'
            self.tree.insert('', tk.END, values=(currency, period, f"{rate:.4f}", source), tags=(tag,))
    
    def on_select(self, event):
        """选中行时填充编辑区"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = self.tree.item(selection[0])
        values = item['values']
        
        if values[3] == '本地':  # 仅本地来源可编辑
            self.currency_entry.delete(0, tk.END)
            self.currency_entry.insert(0, values[0])
            self.currency_entry.config(state='readonly')
            
            self.period_entry.delete(0, tk.END)
            self.period_entry.insert(0, values[1])
            self.period_entry.config(state='readonly')
            
            self.rate_entry.delete(0, tk.END)
            self.rate_entry.insert(0, values[2])
            
            self.status_var.set("已选中本地汇率，可修改或删除")
        else:
            self.currency_entry.config(state='normal')
            self.period_entry.config(state='normal')
            self.status_var.set("GitHub汇率不可直接编辑，请通过添加本地覆盖来修改")
    
    def add_or_update(self):
        """添加或更新本地汇率"""
        currency = self.currency_entry.get().strip().upper()
        period = self.period_entry.get().strip()
        rate_str = self.rate_entry.get().strip()
        
        if not currency:
            messagebox.showwarning("提示", "请输入币种")
            return
        if not period:
            messagebox.showwarning("提示", "请输入结算周期")
            return
        if not rate_str:
            messagebox.showwarning("提示", "请输入汇率")
            return
        
        try:
            rate = float(rate_str)
            if rate <= 0:
                raise ValueError("汇率必须大于0")
        except ValueError as e:
            messagebox.showwarning("提示", f"汇率格式错误: {e}")
            return
        
        key = f"{currency}_{period}"
        self.local_rates[key] = rate
        self._save_local_rates()
        
        self.status_var.set(f"已保存: {currency} {period} = {rate}")
        self.refresh_tree()
        self.load_filter_options()
        
        # 清空输入
        self.currency_entry.config(state='normal')
        self.period_entry.delete(0, tk.END)
        self.period_entry.config(state='normal')
        self.currency_entry.delete(0, tk.END)
        self.rate_entry.delete(0, tk.END)
    
    def delete_selected(self):
        """删除选中的本地汇率"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选中要删除的行")
            return
        
        item = self.tree.item(selection[0])
        values = item['values']
        
        if values[3] != '本地':
            messagebox.showwarning("提示", "只能删除本地覆盖汇率")
            return
        
        key = f"{values[0]}_{values[1]}"
        
        if messagebox.askyesno("确认", f"确定删除 {values[0]} {values[1]} 的本地覆盖吗？"):
            if key in self.local_rates:
                del self.local_rates[key]
                self._save_local_rates()
                self.status_var.set(f"已删除: {values[0]} {values[1]}")
                self.refresh_tree()
                self.load_filter_options()


# 导入pandas用于汇率管理
import pandas as pd


def main():
    """主函数"""
    try:
        root = tk.Tk()
        
        # 同步配置
        try:
            sync_configs_on_startup(APP_DIR, silent=True)
        except Exception as e:
            print(f"同步配置警告: {e}")
        
        app = LoginWindow(root)
        root.mainloop()
        
    except Exception as e:
        # 如果tk还没创建好，用控制台输出
        error_msg = traceback.format_exc()
        error_file = Path.home() / "BillCleaner" / "logs" / "startup_error.log"
        error_file.parent.mkdir(parents=True, exist_ok=True)
        with open(error_file, 'w', encoding='utf-8') as f:
            f.write(f"{datetime.now()}\n{error_msg}")
        
        try:
            messagebox.showerror("启动错误", f"程序启动失败:\n{e}\n\n详细错误已保存到:\n{error_file}")
        except:
            print(f"启动错误: {e}\n{error_msg}")


if __name__ == "__main__":
    main()
