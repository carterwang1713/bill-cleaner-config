"""
SKU映射引擎
负责FNSKU、SellerSKU、仓库SKU之间的三级映射
"""
import pandas as pd
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
from loguru import logger

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import CACHE_CONFIG


class SKUMappingEngine:
    """
    SKU映射引擎
    
    功能：
    1. 管理SKU三级映射关系（FNSKU → SellerSKU → 仓库SKU）
    2. 支持从Excel/CSV加载映射表
    3. 支持批量映射查询
    4. 缓存映射结果
    
    使用示例：
        mapper = SKUMappingEngine()
        mapper.load_from_file("SKU映射表.xlsx")
        result = mapper.map_sku(df, fnsku_col="FNSKU")
    """
    
    def __init__(self):
        """初始化SKU映射引擎"""
        self._fnsku_to_sellersku: Dict[str, str] = {}
        self._sellersku_to_warehouse: Dict[str, str] = {}
        self._all_mappings: Dict[str, Dict[str, str]] = {}
        self._unmapped_fnsku: set = set()
        self._unmapped_sellersku: set = set()
        
        logger.info("SKU映射引擎初始化完成")
    
    def load_from_dataframe(self, df: pd.DataFrame) -> bool:
        """
        从DataFrame加载映射表
        
        Args:
            df: 映射表DataFrame，应包含 FNSKU, SellerSKU, 仓库SKU 列
            
        Returns:
            加载是否成功
        """
        try:
            # 确保有必要的列
            required_cols = ['FNSKU', 'SellerSKU', '仓库SKU']
            existing = [c for c in required_cols if c in df.columns]
            
            if len(existing) < 2:
                logger.error(f"映射表缺少必要的列，需要: {required_cols}")
                return False
            
            # 加载映射关系
            for _, row in df.iterrows():
                fnsku = str(row.get('FNSKU', '')).strip()
                sellersku = str(row.get('SellerSKU', '')).strip()
                warehouse_sku = str(row.get('仓库SKU', '')).strip()
                
                if fnsku and fnsku != 'nan':
                    self._fnsku_to_sellersku[fnsku] = sellersku if sellersku and sellersku != 'nan' else fnsku
                    
                    if sellersku and sellersku != 'nan':
                        self._sellersku_to_warehouse[sellersku] = warehouse_sku if warehouse_sku and warehouse_sku != 'nan' else sellersku
                        self._all_mappings[fnsku] = {
                            'FNSKU': fnsku,
                            'SellerSKU': sellersku,
                            '仓库SKU': warehouse_sku if warehouse_sku and warehouse_sku != 'nan' else sellersku
                        }
            
            logger.info(f"加载映射表成功: {len(self._fnsku_to_sellersku)} 个FNSKU映射")
            return True
            
        except Exception as e:
            logger.error(f"加载映射表失败: {e}")
            return False
    
    def load_from_file(self, file_path: str) -> bool:
        """
        从文件加载映射表
        
        Args:
            file_path: 文件路径
            
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
            
            return self.load_from_dataframe(df)
            
        except Exception as e:
            logger.error(f"从文件加载映射表失败: {e}")
            return False
    
    def load_from_json(self, json_path: str) -> bool:
        """
        从JSON文件加载映射缓存
        
        Args:
            json_path: JSON文件路径
            
        Returns:
            加载是否成功
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._fnsku_to_sellersku = data.get('fnsku_to_sellersku', {})
            self._sellersku_to_warehouse = data.get('sellersku_to_warehouse', {})
            self._all_mappings = data.get('all_mappings', {})
            
            logger.info(f"从JSON加载映射成功: {len(self._fnsku_to_sellersku)} 个映射")
            return True
            
        except Exception as e:
            logger.error(f"从JSON加载映射失败: {e}")
            return False
    
    def save_to_json(self, file_path: Optional[str] = None) -> bool:
        """
        保存映射到JSON文件
        
        Args:
            file_path: 保存路径
            
        Returns:
            保存是否成功
        """
        try:
            save_path = Path(file_path) if file_path else Path(CACHE_CONFIG.cache_dir) / "sku_mapping.json"
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'fnsku_to_sellersku': self._fnsku_to_sellersku,
                'sellersku_to_warehouse': self._sellersku_to_warehouse,
                'all_mappings': self._all_mappings,
            }
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"映射已保存到: {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存映射失败: {e}")
            return False
    
    def add_mapping(self, fnsku: str, sellersku: str, warehouse_sku: str = None) -> None:
        """
        添加单个映射关系
        
        Args:
            fnsku: FNSKU
            sellersku: SellerSKU
            warehouse_sku: 仓库SKU（可选）
        """
        fnsku = str(fnsku).strip()
        sellersku = str(sellersku).strip()
        warehouse_sku = str(warehouse_sku).strip() if warehouse_sku else sellersku
        
        self._fnsku_to_sellersku[fnsku] = sellersku
        self._sellersku_to_warehouse[sellersku] = warehouse_sku
        self._all_mappings[fnsku] = {
            'FNSKU': fnsku,
            'SellerSKU': sellersku,
            '仓库SKU': warehouse_sku
        }
    
    def map_fnsku_to_sellersku(self, fnsku: str) -> Tuple[str, bool]:
        """
        将FNSKU映射到SellerSKU
        
        Args:
            fnsku: FNSKU
            
        Returns:
            (SellerSKU, 是否成功映射)
        """
        fnsku = str(fnsku).strip()
        
        if fnsku in self._fnsku_to_sellersku:
            return self._fnsku_to_sellersku[fnsku], True
        
        self._unmapped_fnsku.add(fnsku)
        return fnsku, False
    
    def map_sellersku_to_warehouse(self, sellersku: str) -> Tuple[str, bool]:
        """
        将SellerSKU映射到仓库SKU
        
        Args:
            sellersku: SellerSKU
            
        Returns:
            (仓库SKU, 是否成功映射)
        """
        sellersku = str(sellersku).strip()
        
        if sellersku in self._sellersku_to_warehouse:
            return self._sellersku_to_warehouse[sellersku], True
        
        self._unmapped_sellersku.add(sellersku)
        return sellersku, False
    
    def map_full_chain(self, fnsku: str) -> Dict[str, Tuple[str, bool]]:
        """
        完整的三级映射
        
        Args:
            fnsku: FNSKU
            
        Returns:
            {'SellerSKU': (值, 是否成功), '仓库SKU': (值, 是否成功)}
        """
        sellersku, ok1 = self.map_fnsku_to_sellersku(fnsku)
        warehouse, ok2 = self.map_sellersku_to_warehouse(sellersku)
        
        return {
            'SellerSKU': (sellersku, ok1),
            '仓库SKU': (warehouse, ok2)
        }
    
    def map_dataframe(
        self, 
        df: pd.DataFrame,
        fnsku_col: str = "FNSKU",
        sellersku_col: str = "SellerSKU",
        add_sellersku_col: str = "SellerSKU_映射",
        add_warehouse_col: str = "仓库SKU"
    ) -> pd.DataFrame:
        """
        为DataFrame添加SKU映射列
        
        Args:
            df: 原始DataFrame
            fnsku_col: FNSKU列名
            sellersku_col: SellerSKU列名
            add_sellersku_col: 新增SellerSKU映射列名
            add_warehouse_col: 新增仓库SKU列名
            
        Returns:
            添加了映射列的DataFrame
        """
        df = df.copy()
        
        # 添加SellerSKU映射列
        if fnsku_col in df.columns:
            df[add_sellersku_col] = df[fnsku_col].apply(
                lambda x: self.map_fnsku_to_sellersku(str(x))[0] if pd.notna(x) else ''
            )
        
        # 添加仓库SKU列
        # 优先使用SellerSKU映射，如果没有则用原SellerSKU
        source_col = add_sellersku_col if add_sellersku_col in df.columns else sellersku_col
        
        if source_col in df.columns:
            df[add_warehouse_col] = df[source_col].apply(
                lambda x: self.map_sellersku_to_warehouse(str(x))[0] if pd.notna(x) else ''
            )
        
        return df
    
    def get_unmapped_count(self) -> Dict[str, int]:
        """
        获取未映射SKU数量
        
        Returns:
            未映射数量统计
        """
        return {
            'unmapped_fnsku': len(self._unmapped_fnsku),
            'unmapped_sellersku': len(self._unmapped_sellersku),
        }
    
    def get_unmapped_list(self) -> Dict[str, List[str]]:
        """
        获取未映射SKU列表
        
        Returns:
            未映射SKU列表
        """
        return {
            'fnsku': list(self._unmapped_fnsku),
            'sellersku': list(self._unmapped_sellersku),
        }
    
    def export_unmapped_report(self, file_path: str) -> bool:
        """
        导出未映射SKU报告
        
        Args:
            file_path: 报告文件路径
            
        Returns:
            导出是否成功
        """
        try:
            fnsku_list = list(self._unmapped_fnsku)
            sellersku_list = list(self._unmapped_sellersku)
            
            df = pd.DataFrame({
                '未映射类型': ['FNSKU'] * len(fnsku_list) + ['SellerSKU'] * len(sellersku_list),
                'SKU': fnsku_list + sellersku_list,
            })
            
            df.to_excel(file_path, index=False, engine='openpyxl')
            logger.info(f"未映射SKU报告已导出: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出未映射SKU报告失败: {e}")
            return False
    
    @property
    def mapping_count(self) -> int:
        """获取映射总数"""
        return len(self._fnsku_to_sellersku)
    
    def clear_unmapped(self) -> None:
        """清空未映射记录"""
        self._unmapped_fnsku.clear()
        self._unmapped_sellersku.clear()


# 导出类
__all__ = ['SKUMappingEngine']
