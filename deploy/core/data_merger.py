"""
数据合并引擎
负责将多来源、多站点的账单数据进行合并和整合
"""
import pandas as pd
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from loguru import logger
import hashlib

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import BUSINESS_CONFIG


class DataMerger:
    """
    数据合并引擎
    
    功能：
    1. 合并多个DataFrame
    2. 统一列名和数据类型
    3. 去除重复数据
    4. 生成合并报告
    
    使用示例：
        merger = DataMerger()
        merged_df = merger.merge([df1, df2, df3])
        report = merger.get_merge_report()
    """
    
    def __init__(self):
        """初始化数据合并引擎"""
        self._merge_history: List[Dict] = []
        self._duplicate_count = 0
        self._total_merged_rows = 0
        
        logger.info("数据合并引擎初始化完成")
    
    def merge(
        self, 
        dataframes: List[pd.DataFrame],
        on: Optional[List[str]] = None,
        how: str = 'concat',
        drop_duplicates: bool = True,
        sort: bool = True,
        sort_columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        合并多个DataFrame
        
        Args:
            dataframes: DataFrame列表
            on: 关联列（用于join模式）
            how: 合并方式 - 'concat'(连接) 或 'merge'(关联)
            drop_duplicates: 是否去除重复行
            sort: 是否排序
            sort_columns: 排序列
            
        Returns:
            合并后的DataFrame
        """
        if not dataframes:
            logger.warning("没有数据需要合并")
            return pd.DataFrame()
        
        # 过滤空DataFrame
        valid_dfs = [df for df in dataframes if df is not None and not df.empty]
        
        if not valid_dfs:
            logger.warning("所有DataFrame都为空")
            return pd.DataFrame()
        
        if len(valid_dfs) == 1:
            logger.info("只有一个DataFrame，直接返回")
            return valid_dfs[0].copy()
        
        logger.info(f"开始合并 {len(valid_dfs)} 个DataFrame")
        
        # 执行合并
        if how == 'concat':
            merged = pd.concat(valid_dfs, ignore_index=True)
        else:
            # merge模式，只保留第一个和第二个的合并
            merged = valid_dfs[0]
            for df in valid_dfs[1:]:
                if on:
                    merged = pd.merge(merged, df, on=on, how='outer')
                else:
                    merged = pd.concat([merged, df], ignore_index=True)
        
        # 去除重复行
        if drop_duplicates:
            before_count = len(merged)
            merged = merged.drop_duplicates()
            self._duplicate_count = before_count - len(merged)
            
            if self._duplicate_count > 0:
                logger.info(f"去除了 {self._duplicate_count} 行重复数据")
        
        # 排序
        if sort:
            if sort_columns is None:
                # 默认按结算周期排序
                sort_columns = ['结算周期', '站点']
            
            existing_cols = [c for c in sort_columns if c in merged.columns]
            if existing_cols:
                merged = merged.sort_values(existing_cols)
        
        self._total_merged_rows = len(merged)
        self._merge_history.append({
            'source_count': len(valid_dfs),
            'result_rows': len(merged),
            'duplicates_removed': self._duplicate_count,
        })
        
        logger.info(f"合并完成，共 {len(merged)} 行数据")
        return merged
    
    def merge_by_country(
        self, 
        data_dict: Dict[str, pd.DataFrame],
        add_country_column: bool = True
    ) -> pd.DataFrame:
        """
        按国家/站点合并数据
        
        Args:
            data_dict: {国家代码: DataFrame} 字典
            add_country_column: 是否添加站点列
            
        Returns:
            合并后的DataFrame
        """
        dfs = []
        
        for country, df in data_dict.items():
            if df is None or df.empty:
                continue
            
            df = df.copy()
            
            if add_country_column and '站点' not in df.columns:
                df['站点'] = country
            
            dfs.append(df)
        
        if not dfs:
            return pd.DataFrame()
        
        merged = pd.concat(dfs, ignore_index=True)
        logger.info(f"按站点合并完成，共 {len(merged)} 行，来自 {len(data_dict)} 个站点")
        
        return merged
    
    def deduplicate(
        self, 
        df: pd.DataFrame,
        subset: Optional[List[str]] = None,
        keep: str = 'last'
    ) -> Tuple[pd.DataFrame, int]:
        """
        去除重复行
        
        Args:
            df: 原始DataFrame
            subset: 用于判断重复的列
            keep: 保留策略 - 'first', 'last', False
            
        Returns:
            (去重后的DataFrame, 去除的行数)
        """
        if df is None or df.empty:
            return df, 0
        
        before = len(df)
        
        if subset is None:
            # 默认使用关键列判断重复
            key_cols = ['订单号', 'SKU', '数量', '结算周期']
            subset = [c for c in key_cols if c in df.columns]
        
        if subset:
            df = df.drop_duplicates(subset=subset, keep=keep)
        else:
            df = df.drop_duplicates(keep=keep)
        
        removed = before - len(df)
        
        if removed > 0:
            logger.info(f"去除了 {removed} 行重复数据")
        
        return df, removed
    
    def normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化列名
        
        Args:
            df: 原始DataFrame
            
        Returns:
            标准化后的DataFrame
        """
        if df is None or df.empty:
            return df
        
        df = df.copy()
        
        # 清理列名
        new_columns = []
        for col in df.columns:
            # 去除首尾空格
            col = str(col).strip()
            # 统一大小写处理
            # 保留原样，只做清理
            new_columns.append(col)
        
        df.columns = new_columns
        
        return df
    
    def split_by_country(self, df: pd.DataFrame, country_col: str = "站点") -> Dict[str, pd.DataFrame]:
        """
        按国家拆分数据
        
        Args:
            df: 合并后的DataFrame
            country_col: 国家列名
            
        Returns:
            {国家代码: DataFrame} 字典
        """
        if df is None or df.empty:
            return {}
        
        if country_col not in df.columns:
            logger.warning(f"找不到国家列 {country_col}")
            return {"ALL": df}
        
        result = {}
        for country, group in df.groupby(country_col):
            result[country] = group
        
        logger.info(f"按国家拆分完成，共 {len(result)} 个国家/站点")
        
        return result
    
    def get_merge_statistics(self) -> Dict:
        """
        获取合并统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'merge_count': len(self._merge_history),
            'total_merged_rows': self._total_merged_rows,
            'total_duplicates_removed': self._duplicate_count,
            'history': self._merge_history,
        }
    
    def reset_statistics(self) -> None:
        """重置统计信息"""
        self._merge_history.clear()
        self._duplicate_count = 0
        self._total_merged_rows = 0


# 导出类
__all__ = ['DataMerger']
