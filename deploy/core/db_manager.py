"""
数据库管理模块
使用SQLite存储清洗后的账单数据
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import pandas as pd
from loguru import logger


class DatabaseManager:
    """数据库管理器"""
    
    # 序列码分类（固定）
    SEQUENCE_CATEGORIES = {
        '收入': list(range(1, 18)) + [44, 45],  # 1-17, 44, 45
        '费用': list(range(22, 41)) + [46],     # 22-40, 46
        '税费': list(range(41, 44)),             # 41-43
        '提现': list(range(18, 22))              # 18-21
    }
    
    # 凭证科目映射 - 序列码到会计科目的映射关系
    # 格式：sequence_code -> (科目方向, 建议科目, 凭证分类)
    # 凭证分类: 1-收入确认凭证, 2-费用支出凭证, 3-税费凭证, 4-提现凭证
    VOUCHER_ACCOUNT_MAPPING = {
        # 收入类 (序列码1-17, 44, 45) -> 收入确认凭证
        # 1: ('借', '应收账款-X店铺', 1),  # 订单收入
        # 2: ('借', '应收账款-X店铺', 1),  # 货到付款
        # 3: ('借', '应收账款-X店铺', 1),  # 促销
        # 4: ('借', '应收账款-X店铺', 1),  # 礼券
        # 5: ('借', '应收账款-X店铺', 1),  # 买家订单
        # 6: ('借', '应收账款-X店铺', 1),  # 转移
        # 7: ('借', '应收账款-X店铺', 1),  # 退款
        # 8: ('借', '应收账款-X店铺', 1),  # 补偿
        # 9: ('借', '应收账款-X店铺', 1),  # 调整
        # 10: ('借', '应收账款-X店铺', 1), # 订阅
        # 11: ('借', '应收账款-X店铺', 1), # B2B
        # 12: ('借', '应收账款-X店铺', 1), # 多次未被认领
        # 13: ('借', '应收账款-X店铺', 1), # Reimbursement
        # 14: ('借', '应收账款-X店铺', 1), # 亚马逊店铺
        # 15: ('借', '应收账款-X店铺', 1), # 清算
        # 16: ('借', '应收账款-X店铺', 1), # 自由塔
        # 17: ('借', '应收账款-X店铺', 1), # 自由塔退款
        # 44: ('借', '应收账款-X店铺', 1), # 预留
        # 45: ('借', '应收账款-X店铺', 1), # 预留
        
        # 费用类 (序列码18-40，18实际是提现金额，分类已在SEQUENCE_CATEGORIES中调整)
        18: ('借', '销售费用-平台佣金', 2),      # 平台佣金（凭证映射待重写）
        19: ('借', '销售费用-尾程自发货运费', 2), # 尾程自发货运费
        20: ('借', '销售费用-尾程FBA配送费', 2), # 尾程FBA配送费
        21: ('借', '销售费用-头程运费', 2),      # 头程运费
        22: ('借', '销售费用-FBA服务处理费', 2), # FBA服务处理费
        23: ('借', '销售费用-仓储费', 2),       # 仓储费
        24: ('借', '销售费用-广告费', 2),        # 广告费
        25: ('借', '销售费用-促销费', 2),        # 促销费
        26: ('借', '销售费用-优惠活动报名费', 2), # 优惠活动报名费
        27: ('借', '销售费用-退货处理费', 2),    # 退货处理费
        28: ('借', '销售费用-弃置费', 2),        # 弃置费
        29: ('借', '销售费用-移除费', 2),         # 移除费
        30: ('借', '销售费用-退款管理费', 2),     # 退款管理费
        31: ('借', '销售费用-变更费', 2),         # 变更费
        32: ('借', '销售费用-订阅费', 2),         # 订阅费
        33: ('借', '销售费用-推广费', 2),         # 推广费
        34: ('借', '销售费用-优惠券费', 2),        # 优惠券费
        35: ('借', '销售费用-其他费用', 2),       # 其他费用
        36: ('借', '销售费用-服务费', 2),         # 服务费
        37: ('借', '销售费用-月租费', 2),         # 月租费
        38: ('借', '销售费用-仓储费', 2),         # 仓储费(预留)
        39: ('借', '销售费用-其他', 2),           # 其他(预留)
        40: ('借', '销售费用-其他', 2),           # 其他(预留)
        
        # 税费类 (序列码41-43)
        41: ('借', '应交税费-销售税', 3),          # 销售税
        42: ('借', '应交税费-增值税', 3),         # 增值税
        43: ('借', '应交税费-其他税费', 3),       # 其他税费
        
        # 提现类 (序列码46+)
        46: ('贷', '银行存款-X店铺', 4),           # 提现
        47: ('贷', '银行存款-X店铺', 4),          # 转账
        48: ('贷', '银行存款-X店铺', 4),         # 服务费退款
        49: ('贷', '银行存款-X店铺', 4),         # 赔偿金
        50: ('贷', '银行存款-X店铺', 4),         # 预留
    }
    
    # 收入类序列码（用于计算应收账款）
    INCOME_SEQUENCE_CODES = list(range(1, 18)) + [44, 45]
    
    # 凭证分类标题
    VOUCHER_CATEGORY_TITLES = {
        1: '①收入确认凭证',
        2: '②费用支出凭证',
        3: '③税费凭证',
        4: '④提现凭证'
    }
    
    def __init__(self, db_path: str):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建二维数据主表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bills_2d (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site TEXT NOT NULL,
                settlement_period TEXT NOT NULL,
                shop_name TEXT,
                sequence_code INTEGER,
                chinese_meaning TEXT,
                amount REAL,
                currency TEXT,
                amount_usd REAL,
                order_id TEXT,
                sku TEXT,
                product_id TEXT,
                performance_dimension TEXT,
                purchase_cost REAL,
                source_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建多维数据表（交易一览数据来源）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bills_multi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site TEXT NOT NULL,
                settlement_period TEXT NOT NULL,
                shop_name TEXT,
                settlement_date TEXT,
                settlement_id TEXT,
                settlement_type TEXT,
                order_id TEXT,
                sku TEXT,
                order_description TEXT,
                quantity INTEGER,
                site_domain TEXT,
                accounting_type TEXT,
                delivery_method TEXT,
                order_city TEXT,
                order_state TEXT,
                postal_code TEXT,
                tax_mode TEXT,
                product_sales_income REAL,
                product_sales_tax REAL,
                shipping_income REAL,
                shipping_tax REAL,
                gift_wrap_income REAL,
                gift_wrap_tax REAL,
                regulatory_fee REAL,
                regulatory_fee_tax REAL,
                discount_amount REAL,
                discount_tax REAL,
                platform_withheld_tax REAL,
                commission REAL,
                shipping_fee REAL,
                other_transaction_fee REAL,
                other_fee REAL,
                settlement_amount REAL,
                transaction_status TEXT,
                transaction_release_date TEXT,
                matching_helper TEXT,
                chinese_meaning TEXT,
                product_id TEXT,
                asin_mapped TEXT,
                category_l1 TEXT,
                category_l2 TEXT,
                category_l3 TEXT,
                latest_purchase_price REAL,
                purchase_cost REAL,
                source_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建二维原币数据表（v1.1.0新增，结构同bills_2d）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bills_2d_local (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site TEXT NOT NULL,
                settlement_period TEXT NOT NULL,
                shop_name TEXT,
                sequence_code INTEGER,
                chinese_meaning TEXT,
                amount REAL,
                currency TEXT,
                amount_usd REAL DEFAULT 0,
                order_id TEXT,
                sku TEXT,
                product_id TEXT,
                performance_dimension TEXT,
                purchase_cost REAL,
                source_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建多维数据表索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_multi_site_period 
            ON bills_multi(site, settlement_period)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_multi_settlement_type 
            ON bills_multi(site, settlement_period, settlement_type)
        ''')

        # 创建结算周期索引表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settlements (
                site TEXT NOT NULL,
                settlement_period TEXT NOT NULL,
                shop_name TEXT,
                row_count INTEGER,
                source_files TEXT,
                cleaned_at TIMESTAMP,
                status TEXT DEFAULT '正常',
                PRIMARY KEY (site, settlement_period, shop_name)
            )
        ''')
        
        # 创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_site_period 
            ON bills_2d(site, settlement_period)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sequence 
            ON bills_2d(site, settlement_period, sequence_code)
        ''')
        
        # bills_2d_local 表索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_2d_local_site_period 
            ON bills_2d_local(site, settlement_period)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_2d_local_sequence 
            ON bills_2d_local(site, settlement_period, sequence_code)
        ''')
        
        conn.commit()
        
        # 自动迁移：检查并添加缺失的字段
        cursor.execute("PRAGMA table_info(bills_2d)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'purchase_cost' not in columns:
            logger.info("检测到旧表结构，正在添加 purchase_cost 字段...")
            cursor.execute("ALTER TABLE bills_2d ADD COLUMN purchase_cost REAL")
            conn.commit()
            logger.info("purchase_cost 字段添加成功")
        
        conn.close()
        logger.info(f"数据库初始化完成: {self.db_path}")
    
    def check_exists(self, site: str, settlement_period: str, shop_name: str = None) -> bool:
        """
        检查指定站点+结算周期+店铺是否已存在
        
        Args:
            site: 站点
            settlement_period: 结算周期（YYYYMM格式）
            shop_name: 店铺名称
            
        Returns:
            是否存在
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if shop_name:
            cursor.execute('''
                SELECT COUNT(*) FROM settlements 
                WHERE site = ? AND settlement_period = ? AND shop_name = ?
            ''', (site, settlement_period, shop_name))
        else:
            cursor.execute('''
                SELECT COUNT(*) FROM settlements 
                WHERE site = ? AND settlement_period = ? AND (shop_name IS NULL OR shop_name = '')
            ''', (site, settlement_period))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count > 0
    
    def delete_settlement(self, site: str, settlement_period: str, shop_name: str = None) -> bool:
        """
        删除指定站点+结算周期+店铺的数据
        
        Args:
            site: 站点
            settlement_period: 结算周期
            shop_name: 店铺名称
            
        Returns:
            是否成功
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if shop_name:
                # 删除二维明细数据（美元版）
                cursor.execute('''
                    DELETE FROM bills_2d 
                    WHERE site = ? AND settlement_period = ? AND shop_name = ?
                ''', (site, settlement_period, shop_name))
                
                # 删除二维原币明细数据（v1.1.0新增）
                cursor.execute('''
                    DELETE FROM bills_2d_local 
                    WHERE site = ? AND settlement_period = ? AND shop_name = ?
                ''', (site, settlement_period, shop_name))
                
                # 删除多维明细数据
                cursor.execute('''
                    DELETE FROM bills_multi 
                    WHERE site = ? AND settlement_period = ? AND shop_name = ?
                ''', (site, settlement_period, shop_name))
                
                # 删除索引记录
                cursor.execute('''
                    DELETE FROM settlements 
                    WHERE site = ? AND settlement_period = ? AND shop_name = ?
                ''', (site, settlement_period, shop_name))
            else:
                # 删除二维明细数据（美元版）
                cursor.execute('''
                    DELETE FROM bills_2d 
                    WHERE site = ? AND settlement_period = ? AND (shop_name IS NULL OR shop_name = '')
                ''', (site, settlement_period))
                
                # 删除二维原币明细数据（v1.1.0新增）
                cursor.execute('''
                    DELETE FROM bills_2d_local 
                    WHERE site = ? AND settlement_period = ? AND (shop_name IS NULL OR shop_name = '')
                ''', (site, settlement_period))
                
                # 删除多维明细数据
                cursor.execute('''
                    DELETE FROM bills_multi 
                    WHERE site = ? AND settlement_period = ? AND (shop_name IS NULL OR shop_name = '')
                ''', (site, settlement_period))
                
                # 删除索引记录
                cursor.execute('''
                    DELETE FROM settlements 
                    WHERE site = ? AND settlement_period = ? AND (shop_name IS NULL OR shop_name = '')
                ''', (site, settlement_period))
            
            conn.commit()
            conn.close()
            
            logger.info(f"删除数据: {site} {settlement_period}")
            return True
            
        except Exception as e:
            logger.error(f"删除数据失败: {e}")
            return False
    
    def delete_settlements_by_period(self, settlement_period: str) -> int:
        """
        删除指定结算周期下所有数据
        
        Args:
            settlement_period: 结算周期
            
        Returns:
            删除的记录数
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for table in ['bills_2d', 'bills_2d_local', 'bills_multi', 'settlements']:
                cursor.execute(f'DELETE FROM {table} WHERE settlement_period = ?', (settlement_period,))
            
            deleted = cursor.execute('SELECT changes()').fetchone()[0]
            conn.commit()
            conn.close()
            
            logger.info(f"按周期删除数据: {settlement_period}")
            return deleted
        except Exception as e:
            logger.error(f"按周期删除数据失败: {e}")
            return 0
    
    def delete_settlements_by_site_period(self, site: str, settlement_period: str) -> int:
        """
        删除指定站点+结算周期下所有数据
        
        Args:
            site: 站点
            settlement_period: 结算周期
            
        Returns:
            删除的记录数
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for table in ['bills_2d', 'bills_2d_local', 'bills_multi', 'settlements']:
                cursor.execute(f'DELETE FROM {table} WHERE site = ? AND settlement_period = ?', (site, settlement_period))
            
            deleted = cursor.execute('SELECT changes()').fetchone()[0]
            conn.commit()
            conn.close()
            
            logger.info(f"按站点+周期删除数据: {site} {settlement_period}")
            return deleted
        except Exception as e:
            logger.error(f"按站点+周期删除数据失败: {e}")
            return 0
    
    def import_dataframe(self, df: pd.DataFrame, site: str, settlement_period: str, 
                         source_file: str, shop_name: str = None) -> Tuple[bool, str]:
        """
        导入DataFrame到数据库
        
        Args:
            df: 二维数据DataFrame
            site: 站点
            settlement_period: 结算周期
            source_file: 来源文件名
            shop_name: 店铺名称
            
        Returns:
            (是否成功, 消息)
        """
        try:
            # 检查是否已存在
            if self.check_exists(site, settlement_period, shop_name):
                shop_str = f" {shop_name}" if shop_name else ""
                return False, f"{site} {settlement_period}{shop_str} 已存在，需先删除"
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 批量构造数据（避免iterrows逐行遍历）
            # 重要：必须将numpy类型转为Python原生类型，否则SQLite会存为二进制blob
            def _to_native(arr):
                """将numpy数组转为Python原生类型列表"""
                return [int(x) if isinstance(x, (int,)) and hasattr(x, '__numpy_') 
                        else int(x) if hasattr(x, 'item') 
                        else None if pd.isna(x) 
                        else x 
                        for x in arr]
            
            records = list(zip(
                [site] * len(df),
                [settlement_period] * len(df),
                [shop_name] * len(df),
                _to_native(df['账单字段序列码'].values) if '账单字段序列码' in df.columns else [None] * len(df),
                df['中文意思'].fillna('').values.tolist() if '中文意思' in df.columns else [''] * len(df),
                _to_native(df['金额'].fillna(0).values) if '金额' in df.columns else [0] * len(df),
                df['币种'].fillna('').values.tolist() if '币种' in df.columns else [''] * len(df),
                _to_native(df['金额(USD)'].fillna(0).values) if '金额(USD)' in df.columns else [0] * len(df),
                df['订单号'].fillna('').values.tolist() if '订单号' in df.columns else [''] * len(df),
                df['SKU'].fillna('').values.tolist() if 'SKU' in df.columns else [''] * len(df),
                df['产品ID'].fillna('').values.tolist() if '产品ID' in df.columns else [''] * len(df),
                df['绩效表对应维度'].fillna('').values.tolist() if '绩效表对应维度' in df.columns else [''] * len(df),
                _to_native(df['采购成本'].fillna(0).values) if '采购成本' in df.columns else [0] * len(df),
                [source_file] * len(df)
            ))
            
            # 批量插入
            cursor.executemany('''
                INSERT INTO bills_2d 
                (site, settlement_period, shop_name, sequence_code, chinese_meaning, amount, 
                 currency, amount_usd, order_id, sku, product_id, 
                 performance_dimension, purchase_cost, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', records)
            
            # 更新索引表
            cursor.execute('''
                INSERT INTO settlements 
                (site, settlement_period, shop_name, row_count, source_files, cleaned_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (site, settlement_period, shop_name, len(df), json.dumps([source_file]), 
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), '正常'))
            
            conn.commit()
            conn.close()
            
            logger.info(f"导入成功(2d): {site} {settlement_period}, {len(df)} 行")
            return True, f"导入成功，共 {len(df)} 行"
            
        except Exception as e:
            logger.error(f"导入失败: {e}")
            return False, f"导入失败: {str(e)}"
    
    def import_2d_local_dataframe(self, df: pd.DataFrame, site: str, settlement_period: str,
                                   source_file: str, shop_name: str = None) -> Tuple[bool, str]:
        """
        导入二维原币DataFrame到数据库（v1.1.0新增）
        
        Args:
            df: 二维原币数据DataFrame
            site: 站点
            settlement_period: 结算周期
            source_file: 来源文件名
            shop_name: 店铺名称
            
        Returns:
            (是否成功, 消息)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 批量构造数据（避免iterrows逐行遍历）
            # 重要：必须将numpy类型转为Python原生类型，否则SQLite会存为二进制blob
            def _to_native(arr):
                """将numpy数组转为Python原生类型列表"""
                return [int(x) if isinstance(x, (int,)) and hasattr(x, '__numpy_') 
                        else int(x) if hasattr(x, 'item') 
                        else None if pd.isna(x) 
                        else x 
                        for x in arr]
            
            records = list(zip(
                [site] * len(df),
                [settlement_period] * len(df),
                [shop_name] * len(df),
                _to_native(df['账单字段序列码'].values) if '账单字段序列码' in df.columns else [None] * len(df),
                df['中文意思'].fillna('').values.tolist() if '中文意思' in df.columns else [''] * len(df),
                _to_native(df['金额'].fillna(0).values) if '金额' in df.columns else [0] * len(df),
                df['币种'].fillna('').values.tolist() if '币种' in df.columns else [''] * len(df),
                # 原币版 amount_usd 存 0
                [0] * len(df),
                df['订单号'].fillna('').values.tolist() if '订单号' in df.columns else [''] * len(df),
                df['SKU'].fillna('').values.tolist() if 'SKU' in df.columns else [''] * len(df),
                df['产品ID'].fillna('').values.tolist() if '产品ID' in df.columns else [''] * len(df),
                df['绩效表对应维度'].fillna('').values.tolist() if '绩效表对应维度' in df.columns else [''] * len(df),
                _to_native(df['采购成本'].fillna(0).values) if '采购成本' in df.columns else [0] * len(df),
                [source_file] * len(df)
            ))
            
            # 批量插入到 bills_2d_local 表
            cursor.executemany('''
                INSERT INTO bills_2d_local 
                (site, settlement_period, shop_name, sequence_code, chinese_meaning, amount, 
                 currency, amount_usd, order_id, sku, product_id, 
                 performance_dimension, purchase_cost, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', records)
            
            conn.commit()
            conn.close()
            
            logger.info(f"导入成功(2d_local): {site} {settlement_period}, {len(df)} 行")
            return True, f"导入成功，共 {len(df)} 行"
            
        except Exception as e:
            logger.error(f"导入失败(2d_local): {e}")
            return False, f"导入失败: {str(e)}"
    
    def import_multi_dataframe(self, df: pd.DataFrame, site: str, settlement_period: str,
                                source_file: str, shop_name: str = None) -> Tuple[bool, str]:
        """
        导入多维DataFrame到数据库
        
        Args:
            df: 多维数据DataFrame（宽表格式）
            site: 站点
            settlement_period: 结算周期（YYYYMM格式）
            source_file: 来源文件名
            shop_name: 店铺名称
        
        Returns:
            (是否成功, 消息)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 多维版列名到数据库字段的映射
            column_mapping = {
                '结算日期': 'settlement_date',
                '结算单号': 'settlement_id',
                '结算类型': 'settlement_type',
                '订单号': 'order_id',
                'SKU': 'sku',
                '订单描述': 'order_description',
                '销量': 'quantity',
                '站点': 'site_domain',
                '核算类型': 'accounting_type',
                '配送方式': 'delivery_method',
                '下单城市': 'order_city',
                '下单州': 'order_state',
                '邮编': 'postal_code',
                '税收缴纳模式': 'tax_mode',
                '商品销售收入': 'product_sales_income',
                '商品销售税': 'product_sales_tax',
                '运费销售收入': 'shipping_income',
                '运费税': 'shipping_tax',
                '包装收入': 'gift_wrap_income',
                '包装税': 'gift_wrap_tax',
                '监管费': 'regulatory_fee',
                '监管费税': 'regulatory_fee_tax',
                '折扣金额': 'discount_amount',
                '折扣税': 'discount_tax',
                '平台代扣代缴税额': 'platform_withheld_tax',
                '佣金': 'commission',
                '运费': 'shipping_fee',
                '其他交易费用': 'other_transaction_fee',
                '其他': 'other_fee',
                '结算金额': 'settlement_amount',
                '交易状态': 'transaction_status',
                '交易放款日期': 'transaction_release_date',
                '匹配辅助列': 'matching_helper',
                '中文意思': 'chinese_meaning',
                '产品ID': 'product_id',
                'ASIN_映射': 'asin_mapped',
                '一级大类': 'category_l1',
                '二级类目': 'category_l2',
                '三级类目': 'category_l3',
                '最新采购价': 'latest_purchase_price',
                '采购成本': 'purchase_cost',
            }
            
            records = []
            # 批量构造数据（避免iterrows逐行遍历）
            columns = [
                'site', 'settlement_period', 'shop_name', 'settlement_date', 'settlement_id',
                'settlement_type', 'order_id', 'sku', 'order_description', 'quantity',
                'site_domain', 'accounting_type', 'delivery_method', 'order_city', 'order_state',
                'postal_code', 'tax_mode', 'product_sales_income', 'product_sales_tax',
                'shipping_income', 'shipping_tax', 'gift_wrap_income', 'gift_wrap_tax',
                'regulatory_fee', 'regulatory_fee_tax', 'discount_amount', 'discount_tax',
                'platform_withheld_tax', 'commission', 'shipping_fee', 'other_transaction_fee',
                'other_fee', 'settlement_amount', 'transaction_status', 'transaction_release_date',
                'matching_helper', 'chinese_meaning', 'product_id', 'asin_mapped',
                'category_l1', 'category_l2', 'category_l3', 'latest_purchase_price',
                'purchase_cost', 'source_file'
            ]
            
            # 反向映射：db字段 -> 中文列名
            reverse_mapping = {v: k for k, v in column_mapping.items()}
            
            # 构建每列的值数组
            col_arrays = []
            for col in columns:
                if col in ('site', 'settlement_period', 'shop_name', 'source_file'):
                    # 固定值列
                    val = {'site': site, 'settlement_period': settlement_period, 
                           'shop_name': shop_name, 'source_file': source_file}[col]
                    col_arrays.append([val] * len(df))
                elif col in reverse_mapping:
                    cn_name = reverse_mapping[col]
                    if cn_name in df.columns:
                        col_arrays.append(df[cn_name].where(df[cn_name].notna(), None).values.tolist())
                    else:
                        col_arrays.append([None] * len(df))
                else:
                    col_arrays.append([None] * len(df))
            
            records = list(zip(*col_arrays))
            
            # 批量插入
            placeholders = ','.join(['?'] * len(columns))
            cursor.executemany(f'''
                INSERT INTO bills_multi 
                ({','.join(columns)})
                VALUES ({placeholders})
            ''', records)
            
            # 更新settlements表的row_count为二维+多维的总行数
            cursor.execute('''
                UPDATE settlements 
                SET row_count = (
                    SELECT COUNT(*) FROM bills_2d 
                    WHERE site = ? AND settlement_period = ? AND (shop_name = ? OR (? IS NULL AND shop_name IS NULL))
                ) + (
                    SELECT COUNT(*) FROM bills_multi 
                    WHERE site = ? AND settlement_period = ? AND (shop_name = ? OR (? IS NULL AND shop_name IS NULL))
                )
                WHERE site = ? AND settlement_period = ? AND (shop_name = ? OR (? IS NULL AND shop_name IS NULL))
            ''', (site, settlement_period, shop_name, shop_name,
                  site, settlement_period, shop_name, shop_name,
                  site, settlement_period, shop_name, shop_name))
            
            conn.commit()
            conn.close()
            
            logger.info(f"导入成功(multi): {site} {settlement_period}, {len(df)} 行")
            return True, f"导入成功，共 {len(df)} 行"
            
        except Exception as e:
            logger.error(f"多维数据导入失败: {e}")
            return False, f"多维数据导入失败: {str(e)}"
    
    def get_settlements_list(self) -> List[Dict]:
        """
        获取所有已导入的结算周期列表
        
        Returns:
            结算周期列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT site, settlement_period, shop_name, row_count, source_files, cleaned_at, status
            FROM settlements
            ORDER BY site, settlement_period DESC, shop_name
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for row in rows:
            result.append({
                'site': row[0],
                'settlement_period': row[1],
                'shop_name': row[2] or '',
                'row_count': row[3],
                'source_files': json.loads(row[4]) if row[4] else [],
                'cleaned_at': row[5],
                'status': row[6]
            })
        
        return result
    
    def get_report_data(self, site: str, settlement_period: str, shop_name: str = None) -> Dict:
        """
        获取对账报表数据
        
        Args:
            site: 站点
            settlement_period: 结算周期
            shop_name: 店铺名称
            
        Returns:
            报表数据字典
        """
        conn = sqlite3.connect(self.db_path)
        
        # 诊断：查一下数据库里到底有什么（v1.1.0改为查bills_2d_local）
        diag_df = pd.read_sql_query('SELECT DISTINCT site, settlement_period, shop_name FROM bills_2d_local LIMIT 20', conn)
        logger.info(f"[对账报表] 数据库中的数据范围: {diag_df.to_dict('records')}")
        logger.info(f"[对账报表] 查询参数: site={site}, period={settlement_period}, shop={shop_name}")
        
        # 查询按序列码分组的汇总（v1.1.0改为查bills_2d_local表，使用原币金额amount）
        if shop_name:
            query = '''
                SELECT sequence_code, chinese_meaning, SUM(amount) as total
                FROM bills_2d_local
                WHERE site = ? AND settlement_period = ? AND shop_name = ?
                GROUP BY sequence_code, chinese_meaning
                ORDER BY sequence_code
            '''
            df = pd.read_sql_query(query, conn, params=(site, settlement_period, shop_name))
        else:
            # shop_name为空时，不限店铺，查询该站点+周期下所有数据
            query = '''
                SELECT sequence_code, chinese_meaning, SUM(amount) as total
                FROM bills_2d_local
                WHERE site = ? AND settlement_period = ?
                GROUP BY sequence_code, chinese_meaning
                ORDER BY sequence_code
            '''
            df = pd.read_sql_query(query, conn, params=(site, settlement_period))
        
        conn.close()
        
        # 修复：SQLite可能存了numpy的二进制blob，需要转换
        def _decode_blob(val):
            """将SQLite中的二进制blob转回整数"""
            if val is None or pd.isna(val):
                return 0
            if isinstance(val, bytes):
                # numpy int64 的二进制表示，8字节小端
                import struct
                try:
                    return struct.unpack('<q', val)[0]
                except:
                    return 0
            try:
                return int(val)
            except:
                return 0
        
        df['sequence_code'] = df['sequence_code'].apply(_decode_blob)
        
        logger.info(f"[对账报表] 修复后: sequence_code示例={df['sequence_code'].head().tolist()}")
        
        if df.empty:
            return None
        
        # sequence_code已在上方通过_decode_blob转换为整数
        
        # 构建报表数据
        report = {
            'summary': {
                '收入合计': 0,
                '费用合计': 0,
                '税费合计': 0,
                '提现合计': 0
            },
            'details': {
                '收入明细': [],
                '费用明细': [],
                '税费明细': [],
                '提现明细': []
            }
        }
        
        # 按分类处理
        for category, seq_codes in self.SEQUENCE_CATEGORIES.items():
            category_df = df[df['sequence_code'].isin(seq_codes)]
            
            total = 0
            details = []
            
            for _, row in category_df.iterrows():
                amount = row['total']
                total += amount
                
                # 借方/贷方分离
                if amount < 0:
                    debit = abs(amount)
                    credit = 0
                else:
                    debit = 0
                    credit = amount
                
                details.append({
                    '序列码': int(row['sequence_code']) if pd.notna(row['sequence_code']) else 0,
                    '项目': row['chinese_meaning'] or '',
                    '借方金额': debit,
                    '贷方金额': credit
                })
            
            # 按序列码排序
            details.sort(key=lambda x: x['序列码'])
            
            report['summary'][f'{category}合计'] = round(total, 2)
            report['details'][f'{category}明细'] = details
        
        return report
    
    def get_sites(self) -> List[str]:
        """获取所有站点列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT DISTINCT site FROM settlements ORDER BY site')
        sites = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return sites
    
    def get_sites_by_period(self, period: str) -> List[str]:
        """
        获取指定结算周期的站点列表
        
        Args:
            period: 结算周期
            
        Returns:
            站点列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT site FROM settlements 
            WHERE settlement_period = ? 
            ORDER BY site
        ''', (period,))
        
        sites = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return sites
    
    def get_periods(self, site: str = None) -> List[str]:
        """
        获取结算周期列表
        
        Args:
            site: 站点（可选，不传则返回所有）
            
        Returns:
            结算周期列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if site:
            cursor.execute('''
                SELECT DISTINCT settlement_period FROM settlements 
                WHERE site = ? 
                ORDER BY settlement_period DESC
            ''', (site,))
        else:
            cursor.execute('''
                SELECT DISTINCT settlement_period FROM settlements 
                ORDER BY settlement_period DESC
            ''')
        
        periods = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return periods
    
    def get_shops(self, site: str, period: str) -> List[str]:
        """
        获取指定站点+结算周期的店铺列表
        
        Args:
            site: 站点
            period: 结算周期
            
        Returns:
            店铺名称列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT shop_name FROM settlements 
            WHERE site = ? AND settlement_period = ?
            ORDER BY shop_name
        ''', (site, period))
        
        shops = [row[0] or '' for row in cursor.fetchall()]
        conn.close()
        
        return shops

    def get_all_periods(self) -> List[str]:
        """获取所有结算周期列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT settlement_period FROM bills_2d 
            ORDER BY settlement_period DESC
        ''')
        
        periods = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return periods
    
    def get_all_sites(self) -> List[str]:
        """获取所有站点列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT site FROM bills_2d 
            ORDER BY site
        ''')
        
        sites = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return sites
    
    def get_all_shops(self) -> List[str]:
        """获取所有店铺列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT shop_name FROM bills_2d 
            WHERE shop_name IS NOT NULL AND shop_name != ''
            ORDER BY shop_name
        ''')
        
        shops = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return shops

    def generate_financial_report(self, settlement_period: str = None, site: str = None, 
                                  shop_name: str = None) -> pd.DataFrame:
        """
        生成财务报表（按绩效维度汇总）
        
        Args:
            settlement_period: 结算周期（可选，不选则汇总所有）
            site: 站点（可选，不选则汇总所有）
            shop_name: 店铺名称（可选，不选则汇总所有）
            
        Returns:
            包含财务指标的DataFrame
        """
        conn = sqlite3.connect(self.db_path)
        
        # 构建查询条件
        conditions = []
        params = []
        
        if settlement_period:
            conditions.append("settlement_period = ?")
            params.append(settlement_period)
        
        if site:
            conditions.append("site = ?")
            params.append(site)
        
        if shop_name:
            conditions.append("shop_name = ?")
            params.append(shop_name)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # 查询按绩效维度汇总的数据
        query = f'''
            SELECT 
                settlement_period,
                site,
                shop_name,
                performance_dimension,
                SUM(amount_usd) as total_amount,
                SUM(purchase_cost) as total_cost
            FROM bills_2d
            WHERE {where_clause}
            GROUP BY settlement_period, site, shop_name, performance_dimension
            ORDER BY settlement_period DESC, site, shop_name, performance_dimension
        '''
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return pd.DataFrame()
        
        # 定义绩效维度到报表列名的映射
        dimension_mapping = {
            '订单金额': '订单金额',
            '退款金额': '平台退款',
            '税费': '税费',
            '平台佣金': '平台佣金',
            '广告费': '广告费',
            '推广费': '推广费',
            '仓储费': '仓储费',
            '尾程派送费': '尾程派送费',
            '弃置费/退货手续费/移除费': '平台退/退货手续费/变更费',
            '售后费用': '售后费用',
            '索赔': '索赔'
        }
        
        # 按结算周期、站点、店铺分组
        group_cols = ['settlement_period', 'site', 'shop_name']
        result_groups = []
        
        for (period, site_val, shop_val), group_df in df.groupby(group_cols, dropna=False):
            row = {
                '结算周期': period,
                '站点': site_val,
                '店铺': shop_val if pd.notna(shop_val) else '',
            }
            
            # 初始化所有财务指标为0
            for col in ['订单金额', '平台退款', '税费', '平台佣金', '广告费', '推广费', 
                       '仓储费', '尾程派送费', '平台退/退货手续费/变更费', '售后费用', '索赔']:
                row[col] = 0.0
            
            # 汇总各绩效维度
            for _, record in group_df.iterrows():
                dim = record['performance_dimension']
                amount = record['total_amount'] or 0
                
                if dim in dimension_mapping:
                    target_col = dimension_mapping[dim]
                    row[target_col] = amount
            
            # 商品成本（从purchase_cost汇总）
            row['商品成本'] = group_df['total_cost'].fillna(0).sum()
            
            result_groups.append(row)
        
        if not result_groups:
            return pd.DataFrame()
        
        result_df = pd.DataFrame(result_groups)
        
        # 计算衍生指标
        # 退款比例 = 平台退款 / 订单金额
        result_df['退款比例'] = result_df.apply(
            lambda x: abs(x['平台退款']) / abs(x['订单金额']) if x['订单金额'] != 0 else 0, axis=1
        )
        
        # 订单净额 = 订单金额 - 平台退款
        result_df['订单净额'] = result_df['订单金额'] - abs(result_df['平台退款'])
        
        # 销售占比 = 订单金额 / 订单金额合计 (每行单独时为100%)
        result_df['销售占比'] = 1.0
        
        # 头程成本 - 暂时设为0，如有数据可从映射中获取
        result_df['头程成本'] = 0.0
        
        # 商品毛利率（含物流成本）= (订单净额 - 商品成本 - 头程成本) / 订单净额
        result_df['商品毛利率（含物流成本）'] = result_df.apply(
            lambda x: (x['订单净额'] - x['商品成本'] - x['头程成本']) / x['订单净额'] if x['订单净额'] != 0 else 0, 
            axis=1
        )
        
        # 总成本 = 商品成本 + 头程成本
        result_df['总成本'] = result_df['商品成本'] + result_df['头程成本']
        
        # 店铺费用合计 = 平台佣金 + 推广费 + 广告费 + 仓储费 + 尾程派送费 + 平台退/退货手续费/变更费 + 售后费用 + 税费 + 索赔
        # 费用基本是负数，直接相加
        result_df['店铺费用合计'] = (
            result_df['平台佣金'] + 
            result_df['推广费'] + 
            result_df['广告费'] + 
            result_df['仓储费'] + 
            result_df['尾程派送费'] + 
            result_df['平台退/退货手续费/变更费'] + 
            result_df['售后费用'] + 
            result_df['税费'] + 
            result_df['索赔']
        )
        
        # 毛利 = 订单净额 - 总成本
        result_df['毛利'] = result_df['订单净额'] - result_df['总成本']
        
        # 毛利率 = 毛利 / 订单净额
        result_df['毛利率'] = result_df.apply(
            lambda x: x['毛利'] / x['订单净额'] if x['订单净额'] != 0 else 0, axis=1
        )
        
        # 店铺利润 = 毛利 + 店铺费用合计（费用是负数，所以是减去）
        result_df['店铺利润'] = result_df['毛利'] + result_df['店铺费用合计']
        
        # 店铺利润率 = 店铺利润 / 订单净额
        result_df['店铺利润率'] = result_df.apply(
            lambda x: x['店铺利润'] / x['订单净额'] if x['订单净额'] != 0 else 0, axis=1
        )
        
        # 重新排列列顺序
        column_order = [
            '结算周期', '站点', '店铺', '订单金额', '平台退款', '退款比例', '订单净额', '销售占比',
            '商品成本', '头程成本', '商品毛利率（含物流成本）', '总成本', '毛利', '毛利率',
            '平台佣金', '推广费', '广告费', '仓储费', '尾程派送费', '平台退/退货手续费/变更费',
            '售后费用', '税费', '索赔', '店铺费用合计', '店铺利润', '店铺利润率'
        ]
        
        # 只保留存在的列
        existing_cols = [col for col in column_order if col in result_df.columns]
        result_df = result_df[existing_cols]
        
        return result_df
    
    def get_voucher_data(self, site: str = None, settlement_period: str = None, 
                         shop_name: str = None) -> Dict:
        """
        获取财务凭证数据
        
        Args:
            site: 站点（可选，不传则汇总所有）
            settlement_period: 结算周期（可选，不传则汇总所有）
            shop_name: 店铺名称（可选，不传则汇总所有）
            
        Returns:
            凭证数据字典，包含：
            - summary: 顶部汇总信息
            - settled_vouchers: 已结算凭证明细
            - unsettled_vouchers: 未结算凭证明细
        """
        conn = sqlite3.connect(self.db_path)
        
        # 构建查询条件
        conditions = []
        params = []
        
        if site:
            conditions.append("site = ?")
            params.append(site)
        
        if settlement_period:
            conditions.append("settlement_period = ?")
            params.append(settlement_period)
        
        if shop_name:
            conditions.append("shop_name = ?")
            params.append(shop_name)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # 查询所有符合条件的数据
        query = f'''
            SELECT 
                site,
                settlement_period,
                shop_name,
                sequence_code,
                chinese_meaning,
                SUM(amount) as total_amount,
                SUM(amount_usd) as total_amount_usd,
                currency
            FROM bills_2d
            WHERE {where_clause}
            GROUP BY site, settlement_period, shop_name, sequence_code, chinese_meaning, currency
            ORDER BY site, settlement_period, shop_name, sequence_code
        '''
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return None
        
        # 处理店铺名称
        df['shop_name'] = df['shop_name'].fillna('')
        
        # 确定结算月份格式（取第一个结算周期）
        first_period = df['settlement_period'].iloc[0] if not df.empty else ''
        if len(str(first_period)) == 6:
            settlement_month = f"{str(first_period)[:4]}/{str(first_period)[4:6]}/01"
        else:
            settlement_month = str(first_period)
        
        # 汇总数据
        result = {
            'summary': {
                'site': site if site else df['site'].iloc[0] if not df.empty else '',
                'shop_name': shop_name if shop_name else df['shop_name'].iloc[0] if not df.empty else '',
                'settlement_month': settlement_month,
                'settled_original': 0.0,
                'settled_usd': 0.0,
                'unsettled_original': 0.0,
                'unsettled_usd': 0.0
            },
            'settled_vouchers': {},
            'unsettled_vouchers': {}
        }
        
        # 收入类序列码
        income_codes = self.INCOME_SEQUENCE_CODES
        # 费用类序列码
        expense_codes = list(range(18, 41))
        # 税费类序列码
        tax_codes = list(range(41, 44))
        # 提现类序列码
        withdrawal_codes = list(range(46, 200))
        
        # 初始化凭证分类
        for cat_id in [1, 2, 3, 4]:
            result['settled_vouchers'][cat_id] = []
            result['unsettled_vouchers'][cat_id] = []
        
        # 汇总各科目的金额
        category_totals = {1: {}, 2: {}, 3: {}, 4: {}}
        
        for _, row in df.iterrows():
            seq_code = row['sequence_code'] if pd.notna(row['sequence_code']) else 0
            amount = row['total_amount'] or 0
            amount_usd = row['total_amount_usd'] or 0
            currency = row['currency'] or 'USD'
            
            # 判断是已结算还是未结算
            is_settled = (currency == 'USD' or currency == '')
            
            # 根据序列码确定凭证分类
            if seq_code in income_codes:
                cat_id = 1
                if amount >= 0:
                    subject = '贷-主营业务收入-销售'
                else:
                    subject = '贷-主营业务收入-退款'
            elif seq_code in expense_codes:
                cat_id = 2
                mapping = self.VOUCHER_ACCOUNT_MAPPING.get(int(seq_code), (None, None, None))
                direction, subject_prefix, _ = mapping
                if subject_prefix:
                    subject = f"借-{subject_prefix}"
                else:
                    subject = f"借-销售费用-其他"
            elif seq_code in tax_codes:
                cat_id = 3
                mapping = self.VOUCHER_ACCOUNT_MAPPING.get(int(seq_code), (None, None, None))
                direction, subject_prefix, _ = mapping
                if subject_prefix:
                    subject = f"借-{subject_prefix}"
                else:
                    subject = f"借-应交税费-其他"
            elif seq_code in withdrawal_codes:
                cat_id = 4
                subject = '贷-银行存款'
            else:
                continue
            
            # 累加到对应分类
            if subject not in category_totals[cat_id]:
                category_totals[cat_id][subject] = {
                    'settled_original': 0.0,
                    'settled_usd': 0.0,
                    'unsettled_original': 0.0,
                    'unsettled_usd': 0.0
                }
            
            if is_settled:
                category_totals[cat_id][subject]['settled_original'] += abs(amount_usd)
                category_totals[cat_id][subject]['settled_usd'] += abs(amount_usd)
                result['summary']['settled_original'] += abs(amount_usd)
                result['summary']['settled_usd'] += abs(amount_usd)
            else:
                category_totals[cat_id][subject]['unsettled_original'] += abs(amount)
                category_totals[cat_id][subject]['unsettled_usd'] += abs(amount_usd)
                result['summary']['unsettled_original'] += abs(amount)
                result['summary']['unsettled_usd'] += abs(amount_usd)
        
        # 构建凭证明细
        for cat_id in [1, 2, 3, 4]:
            for subject, amounts in category_totals[cat_id].items():
                if amounts['settled_original'] > 0 or amounts['settled_usd'] > 0:
                    direction = '借' if subject.startswith('借') else '贷'
                    account_name = subject[2:] if len(subject) > 2 else subject
                    result['settled_vouchers'][cat_id].append({
                        'direction': direction,
                        'account': account_name,
                        'original': amounts['settled_original'],
                        'usd': amounts['settled_usd']
                    })
                
                if amounts['unsettled_original'] > 0 or amounts['unsettled_usd'] > 0:
                    direction = '借' if subject.startswith('借') else '贷'
                    account_name = subject[2:] if len(subject) > 2 else subject
                    result['unsettled_vouchers'][cat_id].append({
                        'direction': direction,
                        'account': account_name,
                        'original': amounts['unsettled_original'],
                        'usd': amounts['unsettled_usd']
                    })
        
        # 对每个分类的明细按科目方向和名称排序
        for cat_id in [1, 2, 3, 4]:
            result['settled_vouchers'][cat_id].sort(key=lambda x: (x['direction'], x['account']))
            result['unsettled_vouchers'][cat_id].sort(key=lambda x: (x['direction'], x['account']))
        
        # 汇总金额四舍五入
        result['summary']['settled_original'] = round(result['summary']['settled_original'], 2)
        result['summary']['settled_usd'] = round(result['summary']['settled_usd'], 2)
        result['summary']['unsettled_original'] = round(result['summary']['unsettled_original'], 2)
        result['summary']['unsettled_usd'] = round(result['summary']['unsettled_usd'], 2)
        
        return result
    
    def get_voucher_subjects(self) -> List[Dict]:
        """
        获取所有凭证科目映射（供配置使用）
        
        Returns:
            凭证科目列表
        """
        subjects = []
        for seq_code, (direction, account, category_id) in self.VOUCHER_ACCOUNT_MAPPING.items():
            subjects.append({
                'sequence_code': seq_code,
                'direction': direction,
                'account': account,
                'category_id': category_id,
                'category_title': self.VOUCHER_CATEGORY_TITLES.get(category_id, '')
            })
        return subjects
