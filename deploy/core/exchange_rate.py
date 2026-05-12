"""
汇率处理引擎
负责加载汇率表并进行币种转换计算
"""
import pandas as pd
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
import json
from loguru import logger

# 导入配置
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import CACHE_CONFIG, CLOUD_CONFIG


class ExchangeRateEngine:
    """
    汇率处理引擎
    
    功能：
    1. 加载和管理汇率表
    2. 根据结算周期匹配汇率
    3. 将各币种金额转换为人民币
    
    使用示例：
        engine = ExchangeRateEngine()
        engine.load_rates_from_file("汇率表.xlsx")
        cny_amount = engine.convert_to_cny(100, "USD", "2024-01")
    """
    
    # 默认汇率（当无法获取实时汇率时使用）
    DEFAULT_RATES = {
        "USD": 7.2,
        "CAD": 5.5,
        "MXN": 0.42,
        "BRL": 1.45,
        "GBP": 9.1,
        "EUR": 7.8,
        "JPY": 0.048,
        "AUD": 4.8,
        "INR": 0.086,
        "AED": 1.96,
        "SGD": 5.35,
        "SEK": 0.68,
        "PLN": 1.8,
    }
    
    # 站点代码到币种的映射
    COUNTRY_CURRENCY_MAP = {
        "US": "USD",
        "CA": "CAD",
        "MX": "MXN",
        "BR": "BRL",
        "UK": "GBP",
        "DE": "EUR",
        "FR": "EUR",
        "IT": "EUR",
        "ES": "EUR",
        "NL": "EUR",
        "PL": "PLN",
        "SE": "SEK",
        "JP": "JPY",
        "AU": "AUD",
        "AE": "AED",
        "SG": "SGD",
        "IN": "INR",
    }
    
    def __init__(self):
        """初始化汇率引擎"""
        self._rates_df: Optional[pd.DataFrame] = None
        self._rates_dict: Dict[str, Dict[str, float]] = {}
        self._last_update: Optional[datetime] = None
        self._cache_file = Path(CACHE_CONFIG.cache_dir) / "exchange_rate_latest.json"
        
        logger.info("汇率处理引擎初始化完成")
    
    def load_rates_from_file(self, file_path: str, settlement_period_col: str = "结算周期") -> bool:
        """
        从Excel文件加载汇率表
        
        Args:
            file_path: 汇率表文件路径
            settlement_period_col: 结算周期列名
            
        Returns:
            加载是否成功
        """
        try:
            logger.info(f"开始加载汇率表: {file_path}")
            
            # 读取Excel文件
            self._rates_df = pd.read_excel(file_path, engine='openpyxl')
            
            # 清理列名
            self._rates_df.columns = self._rates_df.columns.str.strip()
            
            # 构建汇率字典 {结算周期: {币种: 汇率}}
            self._rates_dict = {}
            for _, row in self._rates_df.iterrows():
                period = str(row.get(settlement_period_col, "")).strip()
                if not period or period == "nan":
                    continue
                    
                rates = {}
                for currency in self.DEFAULT_RATES.keys():
                    if currency in row.index:
                        rate_value = row[currency]
                        if pd.notna(rate_value):
                            try:
                                rates[currency] = float(rate_value)
                            except (ValueError, TypeError):
                                rates[currency] = self.DEFAULT_RATES.get(currency, 1.0)
                
                if rates:
                    self._rates_dict[period] = rates
            
            self._last_update = datetime.now()
            
            logger.info(f"汇率表加载成功，共 {len(self._rates_dict)} 个结算周期")
            return True
            
        except Exception as e:
            logger.error(f"加载汇率表失败: {e}")
            return False
    
    def load_rates_from_dict(self, rates_data: Dict[str, Dict[str, float]]) -> None:
        """
        从字典加载汇率数据（用于云端同步）
        
        Args:
            rates_data: 汇率数据，格式为 {结算周期: {币种: 汇率}}
        """
        self._rates_dict = rates_data
        self._last_update = datetime.now()
        logger.info(f"从字典加载汇率数据成功，共 {len(self._rates_dict)} 个结算周期")
    
    def load_rates_from_json(self, file_path: str) -> bool:
        """
        从JSON文件加载汇率缓存
        
        Args:
            file_path: JSON文件路径
            
        Returns:
            加载是否成功
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._rates_dict = data.get('rates', {})
                self._last_update = datetime.fromisoformat(data.get('updated_at', datetime.now().isoformat()))
            logger.info(f"从JSON加载汇率缓存成功")
            return True
        except Exception as e:
            logger.error(f"加载汇率JSON失败: {e}")
            return False
    
    def save_rates_to_json(self, file_path: Optional[str] = None) -> bool:
        """
        保存汇率到JSON文件
        
        Args:
            file_path: 保存路径，默认使用缓存路径
            
        Returns:
            保存是否成功
        """
        try:
            save_path = Path(file_path) if file_path else self._cache_file
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'rates': self._rates_dict,
                'updated_at': datetime.now().isoformat(),
            }
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"汇率已保存到: {save_path}")
            return True
        except Exception as e:
            logger.error(f"保存汇率JSON失败: {e}")
            return False
    
    def get_rate(self, currency: str, settlement_period: str) -> float:
        """
        获取指定币种在结算周期的汇率
        
        Args:
            currency: 币种代码（如USD, EUR）
            settlement_period: 结算周期（如2024-01）
            
        Returns:
            汇率值，如果未找到则返回默认值
        """
        # 转换为大写
        currency = currency.upper()
        
        # 精确匹配
        if settlement_period in self._rates_dict:
            rates = self._rates_dict[settlement_period]
            if currency in rates:
                return rates[currency]
        
        # 月份匹配（如2024-01匹配2024年1月）
        for period, rates in self._rates_dict.items():
            if period.startswith(settlement_period[:7] if len(settlement_period) >= 7 else settlement_period):
                if currency in rates:
                    return rates[currency]
        
        # 降级到默认汇率
        default_rate = self.DEFAULT_RATES.get(currency, 1.0)
        logger.warning(f"未找到 {currency}/{settlement_period} 汇率，使用默认汇率: {default_rate}")
        return default_rate
    
    def get_rates_for_period(self, settlement_period: str) -> Dict[str, float]:
        """
        获取指定结算周期的所有汇率
        
        Args:
            settlement_period: 结算周期
            
        Returns:
            该周期的汇率字典
        """
        if settlement_period in self._rates_dict:
            return self._rates_dict[settlement_period].copy()
        
        # 月份匹配
        for period, rates in self._rates_dict.items():
            if period.startswith(settlement_period[:7] if len(settlement_period) >= 7 else settlement_period):
                return rates.copy()
        
        return self.DEFAULT_RATES.copy()
    
    def convert_to_cny(
        self, 
        amount: float, 
        currency: str, 
        settlement_period: str,
        default_if_missing: bool = True
    ) -> float:
        """
        将金额转换为人民币
        
        Args:
            amount: 原始金额
            currency: 币种代码
            settlement_period: 结算周期
            default_if_missing: 未找到汇率时是否使用默认汇率
            
        Returns:
            人民币金额
        """
        if pd.isna(amount) or amount == 0:
            return 0.0
        
        currency = currency.upper()
        rate = self.get_rate(currency, settlement_period)
        
        if rate == 0:
            logger.warning(f"汇率异常 {currency}/{settlement_period}，返回原值")
            return amount if default_if_missing else 0.0
        
        return round(amount * rate, 2)
    
    def convert_batch_to_cny(
        self, 
        df: pd.DataFrame,
        amount_col: str,
        currency_col: str,
        period_col: str,
        result_col: str = "人民币金额"
    ) -> pd.DataFrame:
        """
        批量转换金额为人民币
        
        Args:
            df: 数据DataFrame
            amount_col: 金额列名
            currency_col: 币种列名
            period_col: 结算周期列名
            result_col: 结果列名
            
        Returns:
            添加了人民币金额列的DataFrame
        """
        df = df.copy()
        df[result_col] = df.apply(
            lambda row: self.convert_to_cny(
                row.get(amount_col, 0),
                str(row.get(currency_col, 'USD')).upper(),
                str(row.get(period_col, ''))
            ),
            axis=1
        )
        return df
    
    def add_currency_column(self, df: pd.DataFrame, country_col: str = "站点") -> pd.DataFrame:
        """
        根据站点添加币种列
        
        Args:
            df: 数据DataFrame
            country_col: 站点列名
            
        Returns:
            添加了币种列的DataFrame
        """
        df = df.copy()
        df['币种'] = df[country_col].map(self.COUNTRY_CURRENCY_MAP).fillna('USD')
        return df
    
    def get_country_currency(self, country_code: str) -> str:
        """
        获取站点对应的币种
        
        Args:
            country_code: 站点代码
            
        Returns:
            币种代码
        """
        return self.COUNTRY_CURRENCY_MAP.get(country_code.upper(), 'USD')
    
    @property
    def available_periods(self) -> List[str]:
        """获取所有可用的结算周期"""
        return sorted(self._rates_dict.keys())
    
    @property
    def last_update(self) -> Optional[datetime]:
        """获取最后更新时间"""
        return self._last_update
    
    def is_cache_valid(self, max_age_hours: int = 24) -> bool:
        """
        检查缓存是否有效
        
        Args:
            max_age_hours: 最大缓存有效期（小时）
            
        Returns:
            缓存是否有效
        """
        if not self._last_update:
            return False
        
        age = datetime.now() - self._last_update
        return age < timedelta(hours=max_age_hours)


# 导出类
__all__ = ['ExchangeRateEngine']
