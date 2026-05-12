"""
匹配辅助列引擎
负责生成匹配辅助列和中文意思映射
"""
import pandas as pd
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
from loguru import logger

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import CACHE_CONFIG


class MatchingHelper:
    """
    匹配辅助列引擎
    
    功能：
    1. 生成匹配辅助列
    2. 中英文结算类型对照
    3. 商品类型识别
    4. 订单类型判断
    
    使用示例：
        helper = MatchingHelper()
        helper.load_chinese_mapping("中文对照表.xlsx")
        df = helper.add_matching_column(df)
    """
    
    # 结算类型中英文对照
    SETTLEMENT_TYPE_MAP = {
        # 英文
        "Order": "订单",
        "Refund": "退款",
        "Adjustment": "调整",
        "Service Fee": "服务费",
        "Subscription": "订阅",
        "Storage Fee": "仓储费",
        "Fulfillment Fee": "配送费",
        "Commission": "佣金",
        "Shipping Charge": "运费",
        "Gift Wrap Charge": "礼品包装费",
        "Promotional Rebate": "促销返利",
        "Lightning Deal": "秒杀",
        # 德文
        "Bestellung": "订单",
        "Erstattung": "退款",
        "Anpassung": "调整",
        "Servicegebühr": "服务费",
        # 法文
        "Commande": "订单",
        "Remboursement": "退款",
        "Ajustement": "调整",
        # 日文
        "注文": "订单",
        "返金": "退款",
        # 中文（保留原样）
        "订单": "订单",
        "退款": "退款",
    }
    
    # 金额类型映射
    AMOUNT_TYPE_MAP = {
        # 英文
        "Product Sales": "商品销售收入",
        "Shipping Credits": "运费收入",
        "Gift Wrap Credits": "礼品包装收入",
        "Promotional Rebates": "促销返利",
        "Marketplace Facilitator Tax": "税费",
        "FBA Inventory Reimbursement": "FBA赔偿",
        "Refund": "退款金额",
        "Service Fee": "服务费",
        "Subscription Fee": "订阅费",
        "Storage Fee": "仓储费",
        "Long Term Storage Fee": "长期仓储费",
        "Fulfillment Fee": "配送费",
        "Weight Based Shipping Fee": "重量配送费",
        "Order Handling Fee": "订单处理费",
        "Pick & Pack Fee": "分拣费",
        "Storage Reservation Fee": "仓储预留费",
    }
    
    def __init__(self):
        """初始化匹配辅助列引擎"""
        self._custom_type_map: Dict[str, str] = {}
        self._custom_amount_map: Dict[str, str] = {}
        self._cache_file = Path(CACHE_CONFIG.cache_dir) / "chinese_mapping.json"
        # 无需关注description的type列表
        self._no_desc_types: List[str] = []
        # 需关注部分description的规则
        self._partial_desc_rules: Dict[str, str] = {}
        
        logger.info("匹配辅助列引擎初始化完成")
    
    def load_chinese_mapping_from_dict(self, mapping_data: Dict[str, str]) -> bool:
        """
        从字典加载中文映射表
        
        Args:
            mapping_data: 映射数据字典，格式为 {原值: 中文值}
            
        Returns:
            加载是否成功
        """
        try:
            for source, target in mapping_data.items():
                self._custom_type_map[source.lower()] = target
            
            logger.info(f"从字典加载中文映射成功: {len(mapping_data)} 条")
            return True
            
        except Exception as e:
            logger.error(f"从字典加载中文映射失败: {e}")
            return False
    
    def load_chinese_mapping_from_file(self, file_path: str) -> bool:
        """
        从文件加载中文映射表
        
        Args:
            file_path: 映射表文件路径
            
        Returns:
            加载是否成功
        """
        try:
            df = pd.read_excel(file_path, engine='openpyxl')
            df.columns = df.columns.str.strip()
            
            # 识别列名
            source_col = None
            target_col = None
            mapping_type_col = None
            
            for col in df.columns:
                col_lower = col.lower()
                if '英文' in col or '原' in col or 'source' in col_lower:
                    source_col = col
                elif '中文' in col or '目标' in col or 'target' in col_lower:
                    target_col = col
                elif '类型' in col or 'type' in col_lower:
                    mapping_type_col = col
            
            if not source_col or not target_col:
                logger.error("映射表缺少必要的列")
                return False
            
            # 加载映射
            for _, row in df.iterrows():
                source = str(row[source_col]).strip()
                target = str(row[target_col]).strip()
                map_type = str(row.get(mapping_type_col, 'settlement')).strip()
                
                if map_type in ['settlement', '结算类型']:
                    self._custom_type_map[source.lower()] = target
                elif map_type in ['amount', '金额类型']:
                    self._custom_amount_map[source.lower()] = target
            
            logger.info(f"加载中文映射成功: {len(self._custom_type_map)} 个结算类型, {len(self._custom_amount_map)} 个金额类型")
            return True
            
        except Exception as e:
            logger.error(f"加载中文映射失败: {e}")
            return False
    
    def save_chinese_mapping(self, file_path: Optional[str] = None) -> bool:
        """
        保存中文映射到文件
        
        Args:
            file_path: 保存路径
            
        Returns:
            保存是否成功
        """
        try:
            save_path = Path(file_path) if file_path else self._cache_file
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'settlement_type_map': {**self.SETTLEMENT_TYPE_MAP, **self._custom_type_map},
                'amount_type_map': {**self.AMOUNT_TYPE_MAP, **self._custom_amount_map},
            }
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"中文映射已保存到: {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存中文映射失败: {e}")
            return False
    
    def translate_settlement_type(self, settlement_type: str) -> str:
        """
        翻译结算类型为中文
        
        Args:
            settlement_type: 原始结算类型
            
        Returns:
            中文结算类型
        """
        if not settlement_type or pd.isna(settlement_type):
            return ""
        
        type_str = str(settlement_type).strip()
        type_lower = type_str.lower()
        
        # 优先查找自定义映射
        if type_lower in self._custom_type_map:
            return self._custom_type_map[type_lower]
        
        # 查找内置映射
        if type_lower in self.SETTLEMENT_TYPE_MAP:
            return self.SETTLEMENT_TYPE_MAP[type_lower]
        
        # 模糊匹配
        for key, value in self.SETTLEMENT_TYPE_MAP.items():
            if key.lower() in type_lower or type_lower in key.lower():
                return value
        
        # 无法匹配，返回原值
        return type_str
    
    def translate_amount_type(self, amount_type: str) -> str:
        """
        翻译金额类型为中文
        
        Args:
            amount_type: 原始金额类型
            
        Returns:
            中文金额类型
        """
        if not amount_type or pd.isna(amount_type):
            return ""
        
        type_str = str(amount_type).strip()
        type_lower = type_str.lower()
        
        # 优先查找自定义映射
        if type_lower in self._custom_amount_map:
            return self._custom_amount_map[type_lower]
        
        # 查找内置映射
        if type_lower in self.AMOUNT_TYPE_MAP:
            return self.AMOUNT_TYPE_MAP[type_lower]
        
        # 模糊匹配
        for key, value in self.AMOUNT_TYPE_MAP.items():
            if key.lower() in type_lower or type_lower in key.lower():
                return value
        
        return type_str
    
    def add_matching_column(
        self,
        df: pd.DataFrame,
        settlement_col: str = "settlement-type",
        amount_type_col: str = "amount-description",
        order_id_col: str = "order-id"
    ) -> pd.DataFrame:
        """
        添加匹配辅助列
        
        Args:
            df: 原始DataFrame
            settlement_col: 结算类型列名
            amount_type_col: 金额类型列名
            order_id_col: 订单号列名
            
        Returns:
            添加了辅助列的DataFrame
        """
        df = df.copy()
        
        # 确定实际列名（尝试多种可能的列名）
        type_col = self._find_column(df, settlement_col, ['settlement-type', 'type', '结算类型', 'Transaction Type'])
        desc_col = self._find_column(df, amount_type_col, ['amount-description', 'description', '金额类型', 'Item Description', '订单描述'])
        order_col = self._find_column(df, order_id_col, ['order-id', 'order id', '订单号'])
        
        # 生成匹配辅助列
        matching_col = "匹配辅助列"
        chinese_meaning_col = "中文意思"
        seq_col = "账单字段序列码"
        perf_dim_col = "绩效表对应维度"
        df[matching_col] = ""
        df[chinese_meaning_col] = ""
        df[seq_col] = ""
        df[perf_dim_col] = ""
        
        if type_col and type_col in df.columns:
            type_lower = type_col.lower()
            
            for idx, row in df.iterrows():
                type_val = str(row.get(type_col, '')).strip()
                type_val_lower = type_val.lower()
                desc_val = str(row.get(desc_col, '')).strip() if desc_col else ''
                desc_val_lower = desc_val.lower()
                
                # 规则1: 无需关注description的type
                if type_val_lower in self._no_desc_types or self._is_no_desc_type(type_val):
                    df.at[idx, matching_col] = type_val
                # 规则2: 需关注部分description的规则
                elif self._check_partial_desc_rule(type_val, desc_val):
                    df.at[idx, matching_col] = self._get_partial_desc_result(type_val, desc_val)
                # 规则3: 默认规则 type/description
                else:
                    if desc_val:
                        df.at[idx, matching_col] = f"{type_val}/{desc_val}"
                    else:
                        df.at[idx, matching_col] = type_val
                
                # 使用中文映射表翻译匹配辅助列为【中文意思】
                matching_val = df.at[idx, matching_col]
                chinese_val = self._translate_with_mapping(matching_val)
                df.at[idx, chinese_meaning_col] = chinese_val
                
                # 获取账单字段序列码和绩效表对应维度
                seq_val, perf_val = self._get_seq_and_perf_dim(matching_val, chinese_val)
                df.at[idx, seq_col] = seq_val
                df.at[idx, perf_dim_col] = perf_val
        
        # 暂时注释掉其他辅助列生成，保持简洁
        # # 翻译结算类型
        # chinese_col = "结算类型_中文"
        # if type_col and type_col in df.columns:
        #     df[chinese_col] = df[type_col].apply(self.translate_settlement_type)
        
        # # 翻译金额类型
        # amount_type_col_name = "金额类型_中文"
        # if desc_col and desc_col in df.columns:
        #     df[amount_type_col_name] = df[desc_col].apply(self.translate_amount_type)
        
        # # 生成订单号辅助列
        # if order_col and order_col in df.columns:
        #     df['订单号_辅助'] = df[order_col].apply(self._extract_order_number)
        
        return df
    
    def _translate_with_mapping(self, matching_val: str) -> str:
        """
        使用中文映射表翻译匹配辅助列值
        
        Args:
            matching_val: 匹配辅助列的值（如 "Order" 或 "Order/Some description"）
            
        Returns:
            中文翻译结果
        """
        if not matching_val or pd.isna(matching_val):
            return ""
        
        matching_str = str(matching_val).strip()
        matching_lower = matching_str.lower()
        
        # 1. 精确匹配（包含大小写变化）
        if matching_lower in self._custom_type_map:
            return self._custom_type_map[matching_lower]
        
        # 2. 原始值匹配
        if matching_str in self._custom_type_map:
            return self._custom_type_map[matching_str]
        
        # 3. 如果没有匹配到精确值，返回原始值
        return matching_str
    
    def _get_seq_and_perf_dim(self, matching_val: str, chinese_val: str) -> tuple:
        """
        获取账单字段序列码和绩效表对应维度
        
        Args:
            matching_val: 匹配辅助列的值
            chinese_val: 中文意思
            
        Returns:
            (账单字段序列码, 绩效表对应维度)
        """
        if not hasattr(self, '_seq_perf_map'):
            # 加载映射表
            import json
            from pathlib import Path
            map_file = Path(__file__).parent.parent / "mappings" / "序列码绩效维度映射.json"
            if map_file.exists():
                with open(map_file, 'r', encoding='utf-8') as f:
                    self._seq_perf_map = json.load(f)
            else:
                self._seq_perf_map = {}
        
        if not matching_val or not chinese_val:
            return ('', '')
        
        # 尝试匹配：匹配辅助列_中文意思
        key = f"{matching_val}_{chinese_val}"
        if key in self._seq_perf_map:
            result = self._seq_perf_map[key]
            return (result.get('账单字段序列码', ''), result.get('绩效表对应维度', ''))
        
        # 尝试小写匹配
        key_lower = key.lower()
        for k, v in self._seq_perf_map.items():
            if k.lower() == key_lower:
                return (v.get('账单字段序列码', ''), v.get('绩效表对应维度', ''))
        
        return ('', '')
    
    def _find_column(self, df: pd.DataFrame, preferred_name: str, alternatives: list) -> str:
        """查找DataFrame中存在的列名"""
        if preferred_name in df.columns:
            return preferred_name
        for alt in alternatives:
            if alt in df.columns:
                return alt
        return None
    
    def _is_no_desc_type(self, type_val: str) -> bool:
        """检查是否为无需关注description的type"""
        if not self._no_desc_types:
            # 默认规则列表（来自规则库）
            default_types = [
                'order', 'refund', 'commande', 'bestellung', 'erstattung',
                'pedido', 'reembolso', 'remboursement', 'ordine', 'rimborso',
                '返金', '注文', 'bestelling', 'terugbetaling', 'zamówienie',
                'zwrot kosztów', 'återbetalning', 'transfer', 'transferer',
                'ubertrag', 'transferir', 'transfert', 'trasferimento',
                '振込み', 'overboeking', 'przelew', 'overforing'
            ]
            return type_val.lower() in default_types
        return type_val.lower() in self._no_desc_types
    
    def _check_partial_desc_rule(self, type_val: str, desc_val: str) -> bool:
        """检查是否匹配部分description规则"""
        if not self._partial_desc_rules:
            return False
        type_lower = type_val.lower()
        desc_lower = desc_val.lower()
        for key in self._partial_desc_rules:
            parts = key.split('|')
            if len(parts) == 2:
                type_cond, desc_cond = parts
                type_match = not type_cond or type_cond in type_lower
                desc_match = desc_cond in desc_lower
                if type_match and desc_match:
                    return True
        return False
    
    def _get_partial_desc_result(self, type_val: str, desc_val: str) -> str:
        """获取部分description规则的结果"""
        type_lower = type_val.lower()
        desc_lower = desc_val.lower()
        for key, result in self._partial_desc_rules.items():
            parts = key.split('|')
            if len(parts) == 2:
                type_cond, desc_cond = parts
                type_match = not type_cond or type_cond in type_lower
                desc_match = desc_cond in desc_lower
                if type_match and desc_match:
                    return result
        return f"{type_val}/{desc_val}" if desc_val else type_val
    
    def _extract_order_number(self, order_id: str) -> str:
        """
        从订单号提取辅助编号
        
        Args:
            order_id: 原始订单号
            
        Returns:
            纯数字订单号
        """
        if not order_id or pd.isna(order_id):
            return ""
        
        # 提取数字部分
        numbers = ''.join(c for c in str(order_id) if c.isdigit())
        return numbers
    
    def classify_transaction(
        self, 
        settlement_type: str,
        amount_type: str = None,
        amount: float = 0
    ) -> str:
        """
        分类交易类型
        
        Args:
            settlement_type: 结算类型
            amount_type: 金额类型
            amount: 金额
            
        Returns:
            交易分类
        """
        chinese_type = self.translate_settlement_type(settlement_type)
        
        if chinese_type in ["订单", "商品销售收入"]:
            return "销售"
        elif chinese_type in ["退款"]:
            return "退款"
        elif chinese_type in ["服务费", "配送费", "仓储费", "佣金"]:
            return "费用"
        elif chinese_type in ["调整"]:
            return "调整"
        else:
            return "其他"
    
    def add_transaction_class(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        添加交易分类列
        
        Args:
            df: DataFrame
            
        Returns:
            添加了交易分类的DataFrame
        """
        df = df.copy()
        
        settlement_col = "结算类型_中文" if "结算类型_中文" in df.columns else "settlement-type"
        
        if settlement_col in df.columns:
            df['交易分类'] = df[settlement_col].apply(
                lambda x: self.classify_transaction(x)
            )
        
        return df
    
    def generate_matching_report(self, df: pd.DataFrame) -> Dict:
        """
        生成匹配报告
        
        Args:
            df: DataFrame
            
        Returns:
            匹配报告字典
        """
        report = {
            'total_rows': len(df),
            'settlement_types': {},
            'amount_types': {},
            'transaction_classes': {},
        }
        
        # 统计结算类型
        if "结算类型_中文" in df.columns:
            report['settlement_types'] = df["结算类型_中文"].value_counts().to_dict()
        
        # 统计金额类型
        if "金额类型_中文" in df.columns:
            report['amount_types'] = df["金额类型_中文"].value_counts().to_dict()
        
        # 统计交易分类
        if "交易分类" in df.columns:
            report['transaction_classes'] = df["交易分类"].value_counts().to_dict()
        
        return report


# 导出类
__all__ = ['MatchingHelper']
