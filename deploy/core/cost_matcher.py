"""
成本匹配引擎 v2.0
支持多种匹配方式：FNSKU、ASIN、sellersku
支持站点维度匹配
支持品类信息（一/二/三级大类）
"""
import pandas as pd
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from loguru import logger

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import CACHE_CONFIG


class CostMatcher:
    """
    采购成本匹配引擎 v2.0
    
    功能：
    1. 加载采购成本表（sellerku、ASIN、FNSKU、站点、仓库sku、一级/二级/三级大类、最新采购价）
    2. 支持三种匹配方式：
       - 清仓收入：通过FNSKU匹配
       - Amazon not found:XXXX：通过ASIN匹配
       - 其他：通过sellersku匹配
    3. 所有匹配必须站点一致
    4. 返回仓库SKU、采购价、一/二/三级大类
    
    使用示例：
        matcher = CostMatcher()
        matcher.load_cost_table("成本表.xlsx")
        df = matcher.match_cost(df, site_col="站点代码", sku_col="SKU", chinese_meaning_col="中文意思")
    """
    
    def __init__(self):
        """初始化成本匹配引擎"""
        # 成本表数据结构
        # _cost_data[站点][sellersku] = {仓库sku, ASIN, FNSKU, 一级大类, 二级大类, 三级大类, 最新采购价}
        self._cost_data: Dict[str, Dict[str, dict]] = {}  # {站点: {sellersku: 成本信息}}
        
        # 索引结构，用于快速查找
        self._fnsku_index: Dict[str, Dict[str, str]] = {}  # {站点: {FNSKU: sellersku}}
        self._asin_index: Dict[str, Dict[str, str]] = {}   # {站点: {ASIN: sellersku}}
        
        self._unmatched_records: List[dict] = []
        self._match_stats: Dict[str, int] = {
            'total': 0,
            'fnsku_match': 0,
            'asin_match': 0,
            'sellersku_match': 0,
            'unmatched': 0
        }
        
        logger.info("成本匹配引擎v2.0初始化完成")
    
    def load_cost_table_from_file(self, file_path: str) -> bool:
        """
        从文件加载采购成本表
        
        Args:
            file_path: 成本表文件路径
            
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
            
            return self.load_cost_table_from_dataframe(df)
            
        except Exception as e:
            logger.error(f"加载采购成本表失败: {e}")
            return False
    
    def load_cost_table_from_dataframe(self, df: pd.DataFrame) -> bool:
        """
        从DataFrame加载成本表
        
        预期列名：sellerku、ASIN、FNSKU、站点、仓库sku、一级大类、二级大类、三级大类、最新采购价
        
        Args:
            df: 成本表DataFrame
            
        Returns:
            加载是否成功
        """
        try:
            # 列名映射（支持多种写法）
            column_mapping = {
                'sellerku': ['sellerku', 'sellersku', 'SellerSKU', '卖家SKU'],
                'ASIN': ['ASIN', 'asin', 'Asin'],
                'FNSKU': ['FNSKU', 'fnsku', 'Fnsku'],
                '站点': ['站点', 'site', 'Site', '站点代码'],
                '仓库sku': ['仓库sku', '仓库SKU', 'warehouse_sku'],
                '一级大类': ['一级大类', '一级分类', 'category_1'],
                '二级大类': ['二级大类', '二级分类', 'category_2'],
                '三级大类': ['三级大类', '三级分类', 'category_3'],
                '最新采购价': ['最新采购价', '采购价', '采购成本', 'cost']
            }
            
            # 查找实际列名
            actual_cols = {}
            for key, alternatives in column_mapping.items():
                for alt in alternatives:
                    if alt in df.columns:
                        actual_cols[key] = alt
                        break
            
            # 检查必需列
            required_cols = ['sellerku', '站点']
            for col in required_cols:
                if col not in actual_cols:
                    logger.error(f"成本表缺少必需列: {col}")
                    return False
            
            # 加载数据
            self._cost_data.clear()
            self._fnsku_index.clear()
            self._asin_index.clear()
            
            for _, row in df.iterrows():
                site = str(row[actual_cols['站点']]).strip().upper()
                sellersku = str(row[actual_cols['sellerku']]).strip()
                
                if not site or site == 'NAN' or not sellersku or sellersku == 'NAN':
                    continue
                
                # 初始化站点数据
                if site not in self._cost_data:
                    self._cost_data[site] = {}
                    self._fnsku_index[site] = {}
                    self._asin_index[site] = {}
                
                # 构建成本信息
                cost_info = {
                    'sellersku': sellersku,
                    '仓库sku': self._get_value(row, actual_cols, '仓库sku'),
                    'ASIN': self._get_value(row, actual_cols, 'ASIN'),
                    'FNSKU': self._get_value(row, actual_cols, 'FNSKU'),
                    '一级大类': self._get_value(row, actual_cols, '一级大类'),
                    '二级大类': self._get_value(row, actual_cols, '二级大类'),
                    '三级大类': self._get_value(row, actual_cols, '三级大类'),
                    '最新采购价': self._get_numeric_value(row, actual_cols, '最新采购价')
                }
                
                # 存储到主数据
                self._cost_data[site][sellersku] = cost_info
                
                # 建立索引
                if cost_info['FNSKU']:
                    self._fnsku_index[site][cost_info['FNSKU']] = sellersku
                if cost_info['ASIN']:
                    self._asin_index[site][cost_info['ASIN']] = sellersku
            
            # 统计信息
            total_sku = sum(len(v) for v in self._cost_data.values())
            total_sites = len(self._cost_data)
            logger.info(f"加载成本表成功: {total_sites}个站点, {total_sku}个SKU")
            
            return True
            
        except Exception as e:
            logger.error(f"加载成本表失败: {e}")
            return False
    
    def _get_value(self, row: pd.Series, col_mapping: dict, key: str) -> str:
        """获取字符串值"""
        if key not in col_mapping:
            return ''
        val = row.get(col_mapping[key], '')
        return str(val).strip() if pd.notna(val) else ''
    
    def _get_numeric_value(self, row: pd.Series, col_mapping: dict, key: str) -> float:
        """获取数值"""
        if key not in col_mapping:
            return 0.0
        try:
            val = row.get(col_mapping[key], 0)
            return float(val) if pd.notna(val) else 0.0
        except:
            return 0.0
    
    def match_single(
        self,
        site: str,
        sku: str,
        chinese_meaning: str = ''
    ) -> Tuple[dict, str]:
        """
        匹配单条记录的成本信息
        
        Args:
            site: 站点代码
            sku: 账单中的SKU
            chinese_meaning: 中文意思（用于判断是否为清仓收入）
            
        Returns:
            (成本信息字典, 匹配方式)
        """
        site = str(site).strip().upper()
        sku = str(sku).strip() if pd.notna(sku) else ''
        chinese_meaning = str(chinese_meaning).strip() if pd.notna(chinese_meaning) else ''
        
        # 默认返回值
        default_result = {
            '仓库sku': '',
            '一级大类': '',
            '二级大类': '',
            '三级大类': '',
            '最新采购价': 0.0
        }
        
        # 检查站点是否存在
        if site not in self._cost_data:
            return default_result, '站点不存在'
        
        # 情况1：清仓收入 → 通过FNSKU匹配
        if '清仓收入' in chinese_meaning:
            result = self._match_by_fnsku(site, sku)
            if result:
                return result, 'FNSKU匹配'
            return default_result, 'FNSKU未匹配'
        
        # 情况2：Amazon not found:XXXX → 通过ASIN匹配
        asin_match = re.match(r'Amazon not found[:\s]+([A-Z0-9]{10})', sku, re.IGNORECASE)
        if asin_match:
            asin = asin_match.group(1).upper()
            result = self._match_by_asin(site, asin)
            if result:
                return result, 'ASIN匹配'
            return default_result, 'ASIN未匹配'
        
        # 情况3：其他 → 通过sellersku匹配
        result = self._match_by_sellersku(site, sku)
        if result:
            return result, 'sellersku匹配'
        
        return default_result, 'sellersku未匹配'
    
    def _match_by_fnsku(self, site: str, fnsku: str) -> Optional[dict]:
        """通过FNSKU匹配"""
        if site not in self._fnsku_index:
            return None
        if fnsku not in self._fnsku_index[site]:
            return None
        sellersku = self._fnsku_index[site][fnsku]
        return self._cost_data[site].get(sellersku)
    
    def _match_by_asin(self, site: str, asin: str) -> Optional[dict]:
        """通过ASIN匹配"""
        if site not in self._asin_index:
            return None
        if asin not in self._asin_index[site]:
            return None
        sellersku = self._asin_index[site][asin]
        return self._cost_data[site].get(sellersku)
    
    def _match_by_sellersku(self, site: str, sellersku: str) -> Optional[dict]:
        """通过sellersku匹配"""
        if site not in self._cost_data:
            return None
        return self._cost_data[site].get(sellersku)
    
    def match_cost(
        self,
        df: pd.DataFrame,
        site_col: str = "站点代码",
        sku_col: str = "SKU",
        chinese_meaning_col: str = "中文意思"
    ) -> pd.DataFrame:
        """
        批量匹配采购成本
        
        Args:
            df: 账单DataFrame
            site_col: 站点列名
            sku_col: SKU列名
            chinese_meaning_col: 中文意思列名
            
        Returns:
            添加了成本信息的DataFrame
        """
        df = df.copy()
        
        # 重置统计
        self._match_stats = {
            'total': 0,
            'fnsku_match': 0,
            'asin_match': 0,
            'sellersku_match': 0,
            'unmatched': 0
        }
        self._unmatched_records = []
        
        # 初始化新列
        df['仓库sku'] = ''
        df['一级大类'] = ''
        df['二级大类'] = ''
        df['三级大类'] = ''
        df['最新采购价'] = 0.0
        df['成本匹配方式'] = ''
        
        # 批量匹配
        for idx, row in df.iterrows():
            site = row.get(site_col, '')
            sku = row.get(sku_col, '')
            chinese_meaning = row.get(chinese_meaning_col, '')
            
            result, match_type = self.match_single(site, sku, chinese_meaning)
            
            df.at[idx, '仓库sku'] = result['仓库sku']
            df.at[idx, '一级大类'] = result['一级大类']
            df.at[idx, '二级大类'] = result['二级大类']
            df.at[idx, '三级大类'] = result['三级大类']
            df.at[idx, '最新采购价'] = result['最新采购价']
            df.at[idx, '成本匹配方式'] = match_type
            
            # 统计
            self._match_stats['total'] += 1
            if 'FNSKU' in match_type:
                self._match_stats['fnsku_match'] += 1
            elif 'ASIN' in match_type:
                self._match_stats['asin_match'] += 1
            elif 'sellersku匹配' in match_type:
                self._match_stats['sellersku_match'] += 1
            else:
                self._match_stats['unmatched'] += 1
                self._unmatched_records.append({
                    '站点': site,
                    'SKU': sku,
                    '中文意思': chinese_meaning,
                    '匹配方式': match_type
                })
        
        # 输出统计
        logger.info(f"成本匹配完成: 总计{self._match_stats['total']}条")
        logger.info(f"  - FNSKU匹配: {self._match_stats['fnsku_match']}条")
        logger.info(f"  - ASIN匹配: {self._match_stats['asin_match']}条")
        logger.info(f"  - sellersku匹配: {self._match_stats['sellersku_match']}条")
        logger.info(f"  - 未匹配: {self._match_stats['unmatched']}条")
        
        return df
    
    def get_match_stats(self) -> Dict[str, int]:
        """获取匹配统计"""
        return self._match_stats.copy()
    
    def get_unmatched_records(self) -> List[dict]:
        """获取未匹配记录"""
        return self._unmatched_records.copy()
    
    def export_unmatched_report(self, file_path: str) -> bool:
        """
        导出未匹配记录报告
        
        Args:
            file_path: 报告文件路径
            
        Returns:
            导出是否成功
        """
        try:
            if not self._unmatched_records:
                logger.info("没有未匹配记录")
                return True
            
            df = pd.DataFrame(self._unmatched_records)
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            logger.info(f"未匹配记录报告已导出: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"导出未匹配报告失败: {e}")
            return False
    
    @property
    def site_count(self) -> int:
        """获取已加载的站点数量"""
        return len(self._cost_data)
    
    @property
    def sku_count(self) -> int:
        """获取已加载的SKU数量"""
        return sum(len(v) for v in self._cost_data.values())


# 导出类
__all__ = ['CostMatcher']
