"""
头程匹配引擎
负责匹配头程运费和税费
"""
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path
from loguru import logger
import json

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import CACHE_CONFIG


class ShippingMatcher:
    """
    头程匹配引擎
    
    功能：
    1. 加载头程费用表
    2. 按订单号/SKU/序列码匹配头程费用
    3. 匹配头程运费和税费
    4. 支持按站点/月份汇总
    
    使用示例：
        matcher = ShippingMatcher()
        matcher.load_shipping_table("头程费用表.xlsx")
        df = matcher.match_shipping(df, order_col="订单号")
    """
    
    def __init__(self):
        """初始化头程匹配引擎"""
        # 匹配键：{(订单号, SKU): {'运费': float, '税费': float}}
        self._shipping_data: Dict[Tuple[str, str], Dict[str, float]] = {}
        # 按订单号匹配
        self._order_shipping: Dict[str, Dict[str, float]] = {}
        # 按SKU匹配
        self._sku_shipping: Dict[str, Dict[str, float]] = {}
        # 默认费用
        self._default_shipping: float = 0.0
        self._default_tax: float = 0.0
        # 未匹配记录
        self._unmatched: List[Dict] = []
        
        logger.info("头程匹配引擎初始化完成")
    
    def load_shipping_table_from_file(
        self, 
        file_path: str,
        order_col: str = "订单号",
        sku_col: str = "SKU",
        shipping_col: str = "头程运费",
        tax_col: str = "头程税费"
    ) -> bool:
        """
        从文件加载头程费用表
        
        Args:
            file_path: 头程费用表文件路径
            order_col: 订单号列名
            sku_col: SKU列名
            shipping_col: 运费列名
            tax_col: 税费列名
            
        Returns:
            加载是否成功
        """
        try:
            file_path = Path(file_path)
            ext = file_path.suffix.lower()
            
            if ext == '.csv':
                df = pd.read_csv(file_path, encoding='utf-8-sig')
            else:
                df = pd.read_excel(file_path, engine='openpyxl')
            
            return self.load_shipping_table_from_dataframe(
                df, order_col, sku_col, shipping_col, tax_col
            )
            
        except Exception as e:
            logger.error(f"加载头程费用表失败: {e}")
            return False
    
    def load_shipping_table_from_dataframe(
        self,
        df: pd.DataFrame,
        order_col: str = "订单号",
        sku_col: str = "SKU",
        shipping_col: str = "头程运费",
        tax_col: str = "头程税费"
    ) -> bool:
        """
        从DataFrame加载头程费用表
        
        Args:
            df: 头程费用表DataFrame
            order_col: 订单号列名
            sku_col: SKU列名
            shipping_col: 运费列名
            tax_col: 税费列名
            
        Returns:
            加载是否成功
        """
        try:
            # 构建索引
            for _, row in df.iterrows():
                order = str(row.get(order_col, '')).strip()
                sku = str(row.get(sku_col, '')).strip()
                shipping = float(row.get(shipping_col, 0)) if pd.notna(row.get(shipping_col)) else 0.0
                tax = float(row.get(tax_col, 0)) if pd.notna(row.get(tax_col)) else 0.0
                
                data = {'运费': shipping, '税费': tax}
                
                # 按订单号存储
                if order and order != 'nan':
                    self._order_shipping[order] = data
                
                # 按SKU存储
                if sku and sku != 'nan':
                    self._sku_shipping[sku] = data
                
                # 按组合存储
                if order and sku and order != 'nan' and sku != 'nan':
                    self._shipping_data[(order, sku)] = data
            
            logger.info(f"加载头程费用表成功: {len(self._order_shipping)} 个订单, {len(self._sku_shipping)} 个SKU")
            return True
            
        except Exception as e:
            logger.error(f"加载头程费用表失败: {e}")
            return False
    
    def load_from_json(self, json_path: str) -> bool:
        """
        从JSON文件加载头程数据
        
        Args:
            json_path: JSON文件路径
            
        Returns:
            加载是否成功
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._order_shipping = data.get('order_shipping', {})
            self._sku_shipping = data.get('sku_shipping', {})
            
            logger.info(f"从JSON加载头程数据成功")
            return True
            
        except Exception as e:
            logger.error(f"从JSON加载头程数据失败: {e}")
            return False
    
    def save_to_json(self, file_path: Optional[str] = None) -> bool:
        """
        保存头程数据到JSON
        
        Args:
            file_path: 保存路径
            
        Returns:
            保存是否成功
        """
        try:
            save_path = Path(file_path) if file_path else Path(CACHE_CONFIG.cache_dir) / "shipping_data.json"
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'order_shipping': self._order_shipping,
                'sku_shipping': self._sku_shipping,
            }
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"头程数据已保存到: {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存头程数据失败: {e}")
            return False
    
    def set_default_fees(self, shipping: float = 0.0, tax: float = 0.0) -> None:
        """
        设置默认费用
        
        Args:
            shipping: 默认运费
            tax: 默认税费
        """
        self._default_shipping = shipping
        self._default_tax = tax
        logger.info(f"设置默认头程费用: 运费={shipping}, 税费={tax}")
    
    def get_shipping(
        self, 
        order: str = None, 
        sku: str = None,
        use_default: bool = True
    ) -> Tuple[float, float, str]:
        """
        获取头程费用
        
        Args:
            order: 订单号
            sku: SKU
            use_default: 未找到时是否使用默认值
            
        Returns:
            (运费, 税费, 匹配方式)
        """
        order = str(order).strip() if order else ''
        sku = str(sku).strip() if sku else ''
        
        # 优先按组合匹配
        if order and sku and (order, sku) in self._shipping_data:
            data = self._shipping_data[(order, sku)]
            return data['运费'], data['税费'], '订单+SKU'
        
        # 按订单号匹配
        if order and order in self._order_shipping:
            data = self._order_shipping[order]
            return data['运费'], data['税费'], '订单号'
        
        # 按SKU匹配
        if sku and sku in self._sku_shipping:
            data = self._sku_shipping[sku]
            return data['运费'], data['税费'], 'SKU'
        
        # 未匹配
        self._unmatched.append({'订单号': order, 'SKU': sku})
        
        if use_default:
            return self._default_shipping, self._default_tax, '默认'
        
        return 0.0, 0.0, '未匹配'
    
    def match_shipping(
        self,
        df: pd.DataFrame,
        order_col: str = "订单号",
        sku_col: str = "SKU",
        shipping_col: str = "头程运费",
        tax_col: str = "头程税费",
        method_col: str = "头程匹配方式",
        add_method: bool = True
    ) -> pd.DataFrame:
        """
        匹配头程费用
        
        Args:
            df: 原始DataFrame
            order_col: 订单号列名
            sku_col: SKU列名
            shipping_col: 运费结果列名
            tax_col: 税费结果列名
            method_col: 匹配方式列名
            add_method: 是否添加匹配方式列
            
        Returns:
            添加了头程费用的DataFrame
        """
        df = df.copy()
        
        shippings = []
        taxes = []
        methods = []
        
        order_col_name = order_col if order_col in df.columns else None
        sku_col_name = sku_col if sku_col in df.columns else None
        
        for idx, row in df.iterrows():
            order = str(row[order_col_name]) if order_col_name else ''
            sku = str(row[sku_col_name]) if sku_col_name else ''
            
            shipping, tax, method = self.get_shipping(order, sku)
            shippings.append(shipping)
            taxes.append(tax)
            methods.append(method)
        
        df[shipping_col] = shippings
        df[tax_col] = taxes
        
        if add_method:
            df[method_col] = methods
        
        matched_count = sum(1 for m in methods if m not in ['默认', '未匹配'])
        logger.info(f"头程费用匹配完成: {matched_count}/{len(df)} 条记录成功匹配")
        
        return df
    
    def aggregate_by_order(
        self, 
        df: pd.DataFrame,
        order_col: str = "订单号",
        amount_cols: List[str] = None
    ) -> pd.DataFrame:
        """
        按订单号汇总金额
        
        Args:
            df: DataFrame
            order_col: 订单号列名
            amount_cols: 需要汇总的金额列
            
        Returns:
            汇总后的DataFrame
        """
        if amount_cols is None:
            amount_cols = ['头程运费', '头程税费']
        
        existing_cols = [c for c in amount_cols if c in df.columns]
        
        if not existing_cols:
            return df
        
        agg_dict = {col: 'sum' for col in existing_cols}
        
        # 添加非金额列
        for col in df.columns:
            if col != order_col and col not in existing_cols:
                agg_dict[col] = 'first'
        
        summarized = df.groupby(order_col, as_index=False).agg(agg_dict)
        
        logger.info(f"按订单汇总完成: {len(summarized)} 个订单")
        
        return summarized
    
    def get_unmatched_records(self) -> List[Dict]:
        """
        获取未匹配记录
        
        Returns:
            未匹配记录列表
        """
        return self._unmatched.copy()
    
    @property
    def order_count(self) -> int:
        """获取已加载的订单数量"""
        return len(self._order_shipping)
    
    @property
    def sku_count(self) -> int:
        """获取已加载的SKU数量"""
        return len(self._sku_shipping)


# 导出类
__all__ = ['ShippingMatcher']
