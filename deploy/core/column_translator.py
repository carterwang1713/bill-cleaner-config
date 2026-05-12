"""
列名翻译引擎
负责将亚马逊账单的多语言列名统一翻译为中文
"""
import pandas as pd
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path
import json
from loguru import logger

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import CACHE_CONFIG


class ColumnTranslator:
    """
    多语言列名翻译器
    
    功能：
    1. 管理多语言列名到中文的映射
    2. 自动识别源语言
    3. 翻译DataFrame列名
    4. 处理未识别的列名
    
    使用示例：
        translator = ColumnTranslator()
        translator.load_mapping_from_file("列名映射表.xlsx")
        translated_df = translator.translate(df, country="DE")
    """
    
    # 多语言列名映射表（英德法西意日荷波瑞典等 -> 中文）
    # 这是一个示例映射，实际数据从云端或本地文件加载
    COLUMN_MAPPING: Dict[str, Dict[str, str]] = {}
    
    # 默认英文列名到中文的映射
    DEFAULT_COLUMN_MAPPING: Dict[str, str] = {
        # 亚马逊账单常见列名
        'settlement-id': '结算ID',
        'transaction-type': '结算类型',
        'order-id': '订单号',
        'order id': '订单号',
        'sku': 'SKU',
        'fnsku': 'FNSKU',
        'asin': 'ASIN',
        'product-name': '商品名称',
        'product name': '商品名称',
        'quantity': '数量',
        'marketplace': '市场',
        'amount': '金额',
        'currency': '货币',
        'amount-type': '金额类型',
        'amount-description': '金额说明',
        'item-description': '商品说明',
        'description': '说明',
        'type': '类型',
        'tax-exclusive-charge': '不含税费用',
        'tax-exclusive-debit': '不含税借方',
        'tax-exclusive-credit': '不含税贷方',
        'tax-charge': '税额',
        'tax-debit': '税目借方',
        'tax-credit': '税目贷方',
        'total': '总计',
        'last-updated': '最后更新',
        'last updated': '最后更新',
    }
    
    # 结算类型中英文对照
    SETTLEMENT_TYPE_MAPPING: Dict[str, str] = {
        # 英文
        "Order": "订单",
        "Refund": "退款",
        "Adjustment": "调整",
        "Service Fee": "服务费",
        "Subscription": "订阅",
        # 德文
        "Bestellung": "订单",
        "Erstattung": "退款",
        "Anpassung": "调整",
        # 法文
        "Commande": "订单",
        "Remboursement": "退款",
        # 日文
        "注文": "订单",
        "返金": "退款",
    }
    
    def __init__(self):
        """初始化列名翻译器"""
        self._mapping_cache: Optional[Dict[str, str]] = None
        self._unmapped_columns: Set[str] = set()
        self._last_country: Optional[str] = None
        self._cache_file = Path(CACHE_CONFIG.cache_dir) / "column_mapping.json"
        
        logger.info("列名翻译引擎初始化完成")
    
    def load_mapping_from_dict(self, mapping_data: Dict[str, Dict[str, str]]) -> None:
        """
        从字典加载映射表（用于云端同步）
        
        Args:
            mapping_data: 映射数据，格式为 {语言代码: {原列名: 中文列名}}
                        或扁平格式: {原列名: 中文列名} (会自动包装到'default'语言下)
        """
        # 检查是否为扁平格式（所有value都是字符串）
        first_value = next(iter(mapping_data.values()), None)
        if first_value is not None and isinstance(first_value, str):
            # 扁平格式，包装到default语言下，并将所有键转为小写
            lower_mapping = {k.lower(): v for k, v in mapping_data.items()}
            self.COLUMN_MAPPING = {'default': lower_mapping}
        else:
            # 嵌套格式，将所有语言的键都转为小写
            lower_mapping = {}
            for lang, mapping in mapping_data.items():
                lower_mapping[lang] = {k.lower(): v for k, v in mapping.items()}
            self.COLUMN_MAPPING = lower_mapping
        self._mapping_cache = None
        logger.info(f"从字典加载列名映射成功，共 {len(mapping_data)} 条规则")
    
    def load_mapping_from_file(self, file_path: str, language_col: str = "语言") -> bool:
        """
        从Excel文件加载列名映射表
        
        Args:
            file_path: 映射表文件路径
            language_col: 语言列名
            
        Returns:
            加载是否成功
        """
        try:
            logger.info(f"开始加载列名映射表: {file_path}")
            
            df = pd.read_excel(file_path, engine='openpyxl')
            df.columns = df.columns.str.strip()
            
            # 按语言分组
            self.COLUMN_MAPPING = {}
            for _, row in df.iterrows():
                lang = str(row.get(language_col, "en")).strip().lower()
                source = str(row.get("原列名", "")).strip()
                target = str(row.get("中文列名", "")).strip()
                
                if not source or not target:
                    continue
                
                if lang not in self.COLUMN_MAPPING:
                    self.COLUMN_MAPPING[lang] = {}
                
                self.COLUMN_MAPPING[lang][source.lower()] = target
            
            # 添加默认英文映射
            if "en" not in self.COLUMN_MAPPING:
                self.COLUMN_MAPPING["en"] = {}
            
            self._mapping_cache = None
            logger.info(f"列名映射表加载成功，共 {len(self.COLUMN_MAPPING)} 种语言")
            return True
            
        except Exception as e:
            logger.error(f"加载列名映射表失败: {e}")
            return False
    
    def save_mapping_to_json(self, file_path: Optional[str] = None) -> bool:
        """
        保存映射到JSON文件
        
        Args:
            file_path: 保存路径
            
        Returns:
            保存是否成功
        """
        try:
            save_path = Path(file_path) if file_path else self._cache_file
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(self.COLUMN_MAPPING, f, ensure_ascii=False, indent=2)
            
            logger.info(f"列名映射已保存到: {save_path}")
            return True
        except Exception as e:
            logger.error(f"保存列名映射失败: {e}")
            return False
    
    def load_mapping_from_json(self, file_path: str) -> bool:
        """
        从JSON文件加载映射
        
        Args:
            file_path: JSON文件路径
            
        Returns:
            加载是否成功
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.COLUMN_MAPPING = json.load(f)
            self._mapping_cache = None
            logger.info(f"从JSON加载列名映射成功")
            return True
        except Exception as e:
            logger.error(f"加载JSON映射失败: {e}")
            return False
    
    def _get_language_for_country(self, country: str) -> str:
        """
        根据国家代码确定语言
        
        Args:
            country: 国家代码
            
        Returns:
            语言代码
        """
        country = country.upper()
        language_map = {
            "US": "en",
            "CA": "en",  # 加拿大支持英法双语，这里默认英文
            "MX": "es",
            "BR": "pt",
            "UK": "en",
            "DE": "de",
            "FR": "fr",
            "IT": "it",
            "ES": "es",
            "NL": "nl",
            "PL": "pl",
            "SE": "sv",
            "JP": "ja",
            "AU": "en",
            "AE": "en",
            "SG": "en",
            "IN": "en",
        }
        return language_map.get(country, "en")
    
    def _get_mapping_for_language(self, language: str) -> Dict[str, str]:
        """
        获取指定语言的映射表
        
        Args:
            language: 语言代码
            
        Returns:
            映射字典
        """
        # 优先精确匹配
        if language in self.COLUMN_MAPPING:
            return self.COLUMN_MAPPING[language]
        
        # 尝试default映射（支持扁平格式的映射表）
        if "default" in self.COLUMN_MAPPING:
            return self.COLUMN_MAPPING["default"]
        
        # 降级到默认英文映射
        if language == "en":
            return self.DEFAULT_COLUMN_MAPPING
        
        # 降级到英文
        if "en" in self.COLUMN_MAPPING:
            return self.COLUMN_MAPPING["en"]
        
        return self.DEFAULT_COLUMN_MAPPING
    
    def translate(self, df: pd.DataFrame, country: Optional[str] = None) -> pd.DataFrame:
        """
        翻译DataFrame列名为中文
        
        Args:
            df: 原始DataFrame
            country: 国家代码，用于确定源语言
            
        Returns:
            翻译后的DataFrame
        """
        if df is None or df.empty:
            logger.warning("输入DataFrame为空，跳过翻译")
            return df
        
        df = df.copy()
        original_columns = df.columns.tolist()
        
        # 确定语言
        language = self._get_language_for_country(country) if country else "en"
        
        # 获取映射表
        mapping = self._get_mapping_for_language(language)
        
        # 翻译列名
        translated_columns = []
        unmapped = []
        
        for col in original_columns:
            col_lower = str(col).strip().lower()
            
            if col_lower in mapping:
                translated_columns.append(mapping[col_lower])
            else:
                # 尝试模糊匹配
                matched = False
                for source, target in mapping.items():
                    if source in col_lower or col_lower in source:
                        translated_columns.append(target)
                        matched = True
                        break
                
                if not matched:
                    translated_columns.append(col)
                    unmapped.append(col)
                    self._unmapped_columns.add(col)
        
        df.columns = translated_columns
        
        if unmapped:
            logger.warning(f"未映射的列名: {unmapped}")
        
        self._last_country = country
        return df
    
    def translate_single(self, column_name: str, language: str = "en") -> str:
        """
        翻译单个列名
        
        Args:
            column_name: 原始列名
            language: 语言代码
            
        Returns:
            中文列名，如果未找到则返回原名
        """
        mapping = self._get_mapping_for_language(language)
        col_lower = str(column_name).strip().lower()
        
        if col_lower in mapping:
            return mapping[col_lower]
        
        # 模糊匹配
        for source, target in mapping.items():
            if source in col_lower or col_lower in source:
                return target
        
        return column_name
    
    def get_mapping(self, language: str = "en") -> Dict[str, str]:
        """
        获取指定语言的完整映射表
        
        Args:
            language: 语言代码
            
        Returns:
            映射字典
        """
        return self._get_mapping_for_language(language).copy()
    
    def add_custom_mapping(self, source: str, target: str, language: str = "en") -> None:
        """
        添加自定义映射
        
        Args:
            source: 源列名
            target: 目标列名
            language: 语言代码
        """
        if language not in self.COLUMN_MAPPING:
            self.COLUMN_MAPPING[language] = {}
        
        self.COLUMN_MAPPING[language][source.lower()] = target
        logger.info(f"添加自定义映射: {language}.{source} -> {target}")
    
    def translate_settlement_type(self, settlement_type: str) -> str:
        """
        翻译结算类型为中文
        
        Args:
            settlement_type: 原始结算类型
            
        Returns:
            中文结算类型
        """
        if not settlement_type:
            return ""
        
        type_lower = str(settlement_type).lower().strip()
        
        # 精确匹配
        if type_lower in self.SETTLEMENT_TYPE_MAPPING:
            return self.SETTLEMENT_TYPE_MAPPING[type_lower]
        
        # 模糊匹配
        for key, value in self.SETTLEMENT_TYPE_MAPPING.items():
            if key.lower() in type_lower or type_lower in key.lower():
                return value
        
        return settlement_type
    
    @property
    def unmapped_columns(self) -> Set[str]:
        """获取所有未映射的列名"""
        return self._unmapped_columns.copy()
    
    def clear_unmapped(self) -> None:
        """清空未映射列名记录"""
        self._unmapped_columns.clear()
    
    @property
    def supported_languages(self) -> List[str]:
        """获取支持的语言列表"""
        return list(self.COLUMN_MAPPING.keys())
    
    def export_unmapped_report(self, file_path: str) -> bool:
        """
        导出未映射列名报告
        
        Args:
            file_path: 报告文件路径
            
        Returns:
            导出是否成功
        """
        try:
            df = pd.DataFrame({
                '未映射列名': list(self._unmapped_columns),
                '建议': ['请检查是否需要添加映射规则'] * len(self._unmapped_columns)
            })
            df.to_excel(file_path, index=False, engine='openpyxl')
            logger.info(f"未映射列名报告已导出: {file_path}")
            return True
        except Exception as e:
            logger.error(f"导出未映射列名报告失败: {e}")
            return False


# 导出类
__all__ = ['ColumnTranslator']
