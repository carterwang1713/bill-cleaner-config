"""
商品映射匹配模块
根据SKU匹配商品信息（产品ID、类目、采购价等）
"""
import pandas as pd
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from loguru import logger


class ProductMatcher:
    """
    商品映射匹配器
    
    功能：
    1. 从商品映射表加载SKU与商品信息的映射关系
    2. 根据SKU匹配产品ID、类目、采购价等信息
    3. 统计未匹配的SKU
    
    使用示例：
        matcher = ProductMatcher()
        matcher.load_from_file("mappings_config/product_mapping.csv")
        df = matcher.match_products(df, sku_col="SKU")
    """
    
    def __init__(self):
        """初始化商品匹配器"""
        self._product_map: Dict[str, Dict] = {}  # SKU -> 商品信息
        self._loaded = False
        self._total_products = 0
        self._unmatched_skus: set = set()
        
        logger.info("商品映射匹配器初始化完成")
    
    def load_from_file(self, file_path: str) -> bool:
        """
        从文件加载商品映射表
        
        Args:
            file_path: 商品映射表文件路径（CSV格式）
            
        Returns:
            加载是否成功
        """
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                logger.warning(f"商品映射表不存在: {file_path}")
                return False
            
            # 读取CSV文件
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            # 检查必需列
            if 'SELLERSKU' not in df.columns:
                logger.error("商品映射表缺少 SELLERSKU 列")
                return False
            
            # 构建映射字典
            self._product_map = {}
            for _, row in df.iterrows():
                sku = str(row.get('SELLERSKU', '')).strip()
                if sku and sku != 'nan':
                    self._product_map[sku] = {
                        'SELLERSKU': sku,
                        'ASIN': str(row.get('ASIN', '')) if pd.notna(row.get('ASIN')) else '',
                        'FNSKU': str(row.get('FNSKU', '')) if pd.notna(row.get('FNSKU')) else '',
                        '站点': str(row.get('站点', '')) if pd.notna(row.get('站点')) else '',
                        '账号': str(row.get('账号', '')) if pd.notna(row.get('账号')) else '',
                        '仓库SKU': str(row.get('仓库SKU', '')) if pd.notna(row.get('仓库SKU')) else '',
                        '产品ID': str(row.get('产品ID', '')) if pd.notna(row.get('产品ID')) else '',
                        '一级大类': str(row.get('一级大类', '')) if pd.notna(row.get('一级大类')) else '',
                        '二级类目': str(row.get('二级类目', '')) if pd.notna(row.get('二级类目')) else '',
                        '三级类目': str(row.get('三级类目', '')) if pd.notna(row.get('三级类目')) else '',
                        '最新采购价': row.get('最新采购价') if pd.notna(row.get('最新采购价')) else None,
                    }
            
            self._loaded = True
            self._total_products = len(self._product_map)
            logger.info(f"加载商品映射表成功: {self._total_products} 个商品")
            return True
            
        except Exception as e:
            logger.error(f"加载商品映射表失败: {e}")
            return False
    
    def match_products(self, df: pd.DataFrame, sku_col: str = 'SKU') -> Tuple[pd.DataFrame, List[str]]:
        """
        匹配商品信息
        
        Args:
            df: 待处理的数据框
            sku_col: SKU列名
            
        Returns:
            (匹配后的数据框, 未匹配的SKU列表)
        """
        if not self._loaded:
            logger.warning("商品映射表未加载，跳过匹配")
            return df, []
        
        if sku_col not in df.columns:
            logger.warning(f"数据中找不到 {sku_col} 列，跳过商品匹配")
            return df, []
        
        # 添加商品信息列
        df['产品ID'] = ''
        df['一级大类'] = ''
        df['二级类目'] = ''
        df['三级类目'] = ''
        df['最新采购价'] = None
        
        matched_count = 0
        self._unmatched_skus = set()
        
        for idx, row in df.iterrows():
            sku = str(row.get(sku_col, '')).strip()
            
            if sku and sku in self._product_map:
                product_info = self._product_map[sku]
                df.at[idx, '产品ID'] = product_info['产品ID']
                df.at[idx, '一级大类'] = product_info['一级大类']
                df.at[idx, '二级类目'] = product_info['二级类目']
                df.at[idx, '三级类目'] = product_info['三级类目']
                if product_info['最新采购价'] is not None:
                    df.at[idx, '最新采购价'] = product_info['最新采购价']
                matched_count += 1
            elif sku and sku != 'nan':
                self._unmatched_skus.add(sku)
        
        match_rate = matched_count / len(df) * 100 if len(df) > 0 else 0
        logger.info(f"商品匹配完成: {matched_count}/{len(df)} ({match_rate:.1f}%)")
        
        if self._unmatched_skus:
            logger.warning(f"未匹配的SKU数量: {len(self._unmatched_skus)}")
        
        return df, list(self._unmatched_skus)
    
    def get_stats(self) -> Dict:
        """
        获取匹配统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'loaded': self._loaded,
            'total_products': self._total_products,
            'unmatched_count': len(self._unmatched_skus),
            'unmatched_skus': list(self._unmatched_skus)[:20],  # 只返回前20个
        }
    
    def is_loaded(self) -> bool:
        """检查是否已加载映射表"""
        return self._loaded
