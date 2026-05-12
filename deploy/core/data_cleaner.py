"""
数据清洗引擎
负责货币格式标准化、空值处理等数据清洗工作
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union, Callable, Tuple
from pathlib import Path
from loguru import logger
import re

import sys
sys.path.append(str(Path(__file__).parent.parent))


class DataCleaner:
    """
    数据清洗引擎
    
    功能：
    1. 货币格式标准化（处理Unicode负号、千分位等）
    2. 空值处理
    3. 数据类型转换
    4. 异常值处理
    
    使用示例：
        cleaner = DataCleaner()
        df = cleaner.clean_dataframe(df, currency_columns=['金额', '运费'])
    """
    
    # Unicode负号字符
    UNICODE_MINUS = ['−', '－', '﹣', '⁻', '₋', '‐', '‑', '‒', '–', '—', '―', '￣', '¯']
    
    # 千分位符号
    THOUSAND_SEPARATORS = ['.', ',', ' ']
    
    # 需要清洗的货币列名关键词
    CURRENCY_COLUMN_KEYWORDS = [
        '金额', '收入', '费用', '退款', '利润', '成本', '运费', 
        '佣金', '税费', '税', '其他', '汇率', '人民币', '监管费'
    ]
    
    def __init__(self):
        """初始化数据清洗引擎"""
        self._cleaned_count = 0
        self._null_converted_count = 0
        self._format_fixed_count = 0
        
        logger.info("数据清洗引擎初始化完成")
    
    def clean_currency_format(self, value: any) -> float:
        """
        清洗单个货币值为标准float
        
        Args:
            value: 原始值
            
        Returns:
            标准化的浮点数
        """
        if pd.isna(value):
            return 0.0
        
        if isinstance(value, (int, float)):
            return float(value)
        
        # 转换为字符串
        str_value = str(value).strip()
        
        if not str_value:
            return 0.0
        
        # 处理括号（负数）
        is_negative = False
        if '(' in str_value and ')' in str_value:
            is_negative = True
            str_value = str_value.replace('(', '').replace(')', '')
        
        # 替换Unicode负号（增强版：支持更多变体）
        unicode_minus_chars = ['−', '－', '﹣', '⁻', '₋', '‐', '‑', '‒', '–', '—', '―', '￣', '¯']
        for uni_minus in unicode_minus_chars:
            if uni_minus in str_value:
                is_negative = True
                str_value = str_value.replace(uni_minus, '-')
        
        # 处理开头负号与数字之间的空格（如: - 11,60 -> -11,60）
        str_value = re.sub(r'-\s+', '-', str_value)
        
        # 去除货币符号（如 $, €, £, ¥）
        str_value = re.sub(r'[$€£¥₹]', '', str_value)
        
        # 去除空格千分位符号 (如: 1 000,50 -> 1000,50 或 -1 000,50 -> -1000,50)
        str_value = re.sub(r'(\d)\s+(\d)', r'\1\2', str_value)
        
        # 判断数字格式并转换为标准格式
        has_comma = ',' in str_value
        has_dot = '.' in str_value
        
        if has_comma and has_dot:
            # 两种分隔符都存在，判断格式
            last_comma = str_value.rfind(',')
            last_dot = str_value.rfind('.')
            
            if last_dot > last_comma:
                # 美式格式: 1,234.56 -> 去除逗号
                str_value = str_value.replace(',', '')
            else:
                # 欧式格式: 1.234,56 -> 去除点，逗号改为点
                str_value = str_value.replace('.', '').replace(',', '.')
        elif has_comma:
            # 只有逗号
            # 判断是千分位还是小数点：检查逗号后面的位数
            parts = str_value.split(',')
            if len(parts) == 2 and len(parts[1]) <= 2:
                # 欧式小数点: 10,50 或 24,79 -> 转换为 10.50 或 24.79
                str_value = str_value.replace(',', '.')
            elif len(parts) == 2 and len(parts[1]) == 3:
                # 可能是欧式千分位带三位小数: 1.234,567 (极少见)
                # 转换为逗号为小数点
                str_value = str_value.replace(',', '.')
            else:
                # 美式千分位: 1,234 -> 去除逗号
                str_value = str_value.replace(',', '')
        elif has_dot:
            # 只有一个点
            parts = str_value.split('.')
            if len(parts) == 2 and len(parts[1]) <= 2 and len(parts[0]) <= 3:
                # 可能是欧式格式被误读为美式: 逗号小数点被读作点
                # 保守处理：保持原样
                pass
            else:
                # 美式格式或整数: 1,234.56 或 1234
                str_value = str_value.replace(',', '')
        
        # 处理欧洲格式的逗号为小数点（关键修复）
        # 如果逗号后只有1-2位数字，且点是千分位，则转换
        if ',' in str_value and '.' in str_value:
            # 这里逗号应该已经是小数点了，如果同时有点，可能是欧式格式
            comma_idx = str_value.rfind(',')
            dot_idx = str_value.rfind('.')
            after_comma = str_value[comma_idx+1:] if comma_idx < len(str_value) - 1 else ''
            after_dot = str_value[dot_idx+1:] if dot_idx < len(str_value) - 1 else ''
            
            # 如果逗号后是1-2位数字，且点后是3位数字（千分位），则转换
            if len(after_comma) <= 2 and len(after_dot) == 3:
                str_value = str_value.replace('.', '').replace(',', '.')
        
        # 尝试解析
        try:
            result = float(str_value)
            if is_negative:
                result = -result
            return round(result, 2)
        except ValueError:
            # 最终兜底方案：直接将逗号替换为点
            str_value_eur = str(value).replace('.', '').replace(',', '.')
            try:
                result = float(str_value_eur)
                if is_negative:
                    result = -result
                return round(result, 2)
            except ValueError:
                logger.warning(f"无法解析货币值: {value}")
                return 0.0
    
    def clean_currency_column(
        self, 
        df: pd.DataFrame, 
        column: str,
        result_column: Optional[str] = None
    ) -> pd.DataFrame:
        """
        清洗货币列
        
        Args:
            df: 原始DataFrame
            column: 需要清洗的列名
            result_column: 结果列名，如果为None则覆盖原列
            
        Returns:
            清洗后的DataFrame
        """
        df = df.copy()
        
        if column not in df.columns:
            logger.warning(f"列不存在: {column}")
            return df
        
        target_col = result_column if result_column else column
        
        if target_col != column:
            df[target_col] = None
        
        df[target_col] = df[column].apply(self.clean_currency_format)
        
        return df
    
    def clean_dataframe(
        self, 
        df: pd.DataFrame,
        currency_columns: Optional[List[str]] = None,
        auto_detect_currency: bool = True,
        fill_na_values: Optional[Dict[str, any]] = None,
        convert_dtypes: bool = True
    ) -> pd.DataFrame:
        """
        批量清洗DataFrame
        
        Args:
            df: 原始DataFrame
            currency_columns: 需要清洗的货币列
            auto_detect_currency: 是否自动检测货币列
            fill_na_values: 空值填充配置，格式 {列名: 填充值}
            convert_dtypes: 是否转换数据类型
            
        Returns:
            清洗后的DataFrame
        """
        df = df.copy()
        
        # 自动检测货币列
        if auto_detect_currency and currency_columns is None:
            currency_columns = self._detect_currency_columns(df)
        
        # 清洗货币列
        if currency_columns:
            for col in currency_columns:
                if col in df.columns:
                    df = self.clean_currency_column(df, col)
                    self._format_fixed_count += df[col].notna().sum()
        
        # 填充空值
        if fill_na_values:
            for col, fill_value in fill_na_values.items():
                if col in df.columns:
                    null_count = df[col].isna().sum()
                    df[col] = df[col].fillna(fill_value)
                    self._null_converted_count += null_count
        
        # 转换数据类型
        if convert_dtypes:
            df = self._convert_column_types(df)
        
        self._cleaned_count += 1
        
        # 提取站点代码
        df = self.extract_site_code(df)
        
        # 添加货币列（从df.attrs中获取）
        if 'currency' in df.attrs:
            df['币种'] = df.attrs['currency']
            logger.info(f"币种列添加完成: {df.attrs['currency']}")
        else:
            df['币种'] = ''
        
        # 处理结算日期
        df = self.process_settlement_date(df)
        
        return df
    
    def extract_site_code(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        从站点列提取站点代码
        
        Args:
            df: DataFrame
            
        Returns:
            添加了站点代码列的DataFrame
        """
        # 查找站点列（多种可能的列名）
        site_col = None
        for col in df.columns:
            col_lower = col.lower()
            if 'site' in col_lower and ('vente' in col_lower or 'sale' in col_lower or col == '站点'):
                site_col = col
                break
        
        if not site_col:
            # 尝试直接找"站点"列
            if '站点' in df.columns:
                site_col = '站点'
        
        if site_col:
            # 站点代码映射：amazon.com.be -> BE, amazon.com -> US, amazon.co.uk -> UK
            def extract_code(site_val):
                if pd.isna(site_val):
                    return ''
                site_str = str(site_val).lower().strip()
                # amazon.com.be -> BE
                if '.be' in site_str:
                    return 'BE'
                # amazon.com -> US
                elif site_str == 'amazon.com' or site_str.endswith('.com'):
                    return 'US'
                # amazon.co.uk -> UK
                elif '.co.uk' in site_str:
                    return 'UK'
                # amazon.de -> DE
                elif site_str.endswith('.de'):
                    return 'DE'
                # amazon.fr -> FR
                elif site_str.endswith('.fr'):
                    return 'FR'
                # amazon.it -> IT
                elif site_str.endswith('.it'):
                    return 'IT'
                # amazon.es -> ES
                elif site_str.endswith('.es'):
                    return 'ES'
                # amazon.nl -> NL
                elif site_str.endswith('.nl'):
                    return 'NL'
                # amazon.pl -> PL
                elif site_str.endswith('.pl'):
                    return 'PL'
                # amazon.se -> SE
                elif site_str.endswith('.se'):
                    return 'SE'
                # amazon.co.jp / amazon.jp -> JP
                elif '.jp' in site_str:
                    return 'JP'
                # amazon.ca -> CA
                elif site_str.endswith('.ca'):
                    return 'CA'
                # amazon.com.mx -> MX
                elif '.mx' in site_str:
                    return 'MX'
                # amazon.com.br -> BR
                elif '.br' in site_str:
                    return 'BR'
                # amazon.in -> IN
                elif site_str.endswith('.in'):
                    return 'IN'
                # amazon.ae -> AE
                elif site_str.endswith('.ae'):
                    return 'AE'
                # amazon.sa -> SA
                elif site_str.endswith('.sa'):
                    return 'SA'
                # amazon.sg -> SG
                elif site_str.endswith('.sg'):
                    return 'SG'
                # amazon.com.au -> AU
                elif '.au' in site_str:
                    return 'AU'
                else:
                    # 尝试从最后一段提取
                    parts = site_str.split('.')
                    if len(parts) > 1:
                        return parts[-1].upper()
                    return ''
            
            df['站点代码'] = df[site_col].apply(extract_code)
            
            # 对于空值，使用众数（出现最多的站点代码）填充
            # 注意：这里计算的是当前CSV文件的众数，每个文件独立处理
            mode_site = df['站点代码'].mode()
            if len(mode_site) > 0 and mode_site.iloc[0]:
                df['站点代码'] = df['站点代码'].replace('', pd.NA).fillna(mode_site.iloc[0])
                logger.info(f"站点代码提取完成，空值填充为: {mode_site.iloc[0]}")
            else:
                logger.info(f"站点代码提取完成: {df['站点代码'].unique().tolist()}")
        else:
            df['站点代码'] = ''
        
        return df
    
    def process_settlement_date(self, df: pd.DataFrame, date_column: str = '结算日期') -> pd.DataFrame:
        """
        处理结算日期列，提取结算周期
        
        Args:
            df: DataFrame
            date_column: 结算日期列名
            
        Returns:
            添加了结算时间列的DataFrame
        """
        # 多语言月份映射
        month_map = {
            # 英语
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
            'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
            # 法语
            'janv': '01', 'févr': '02', 'mars': '03', 'avr': '04', 'mai': '05',
            'juin': '06', 'juil': '07', 'août': '08', 'sept': '09', 'oct': '10', 'nov': '11', 'déc': '12',
            # 西班牙语
            'ene': '01', 'abr': '04', 'ago': '08', 'dic': '12',
            # 意大利语
            'gen': '01', 'mag': '05', 'giu': '06', 'lug': '07', 'set': '09', 'ott': '10',
            # 波兰语
            'sty': '01', 'lut': '02', 'kwi': '04', 'maj': '05', 'cze': '06',
            'lip': '07', 'sie': '08', 'wrz': '09', 'paź': '10', 'lis': '11', 'gru': '12',
            # 荷兰语
            'okt': '10', 'mrt': '03', 'mei': '05', 'juni': '06', 'juli': '07',
            # 德语
            'mär': '03', 'märz': '03', 'mai': '05', 'dez': '12',
        }
        
        df = df.copy()
        
        if date_column not in df.columns:
            logger.warning(f"未找到结算日期列: {date_column}")
            return df
        
        def process_date(date_str):
            """处理单个日期字符串"""
            if pd.isna(date_str) or not str(date_str).strip():
                return ''
            
            date_str = str(date_str).strip()
            
            # 按空格、逗号、点号分列
            parts = date_str.replace(',', ' ').replace('.', ' ').split()
            
            # UTC格式：如 "1 mars 2026 21:09:22 UTC"
            if 'UTC' in date_str:
                if len(parts) >= 3:
                    try:
                        day = parts[0].zfill(2)
                        month_str = parts[1].lower()
                        year = parts[2]
                        month = month_map.get(month_str, month_str).zfill(2)
                        return f"{year}/{month}/{day}"
                    except:
                        pass
            
            # PST/PDT格式：如 "Mar 1, 2026 1:09:22 PM PST"
            elif 'PST' in date_str or 'PDT' in date_str:
                if len(parts) >= 3:
                    try:
                        month_str = parts[0].lower()
                        day = parts[1].replace(',', '').zfill(2)
                        year = parts[2]
                        month = month_map.get(month_str, month_str).zfill(2)
                        return f"{year}/{month}/{day}"
                    except:
                        pass
            
            # JST格式：如 "2026/03/01"
            elif 'JST' in date_str:
                if len(parts) >= 1:
                    return parts[0]
            
            # 纯数字格式：如 "01032026"
            elif len(date_str) >= 8:
                digits = re.findall(r'\d+', date_str)
                for digit_str in digits:
                    if len(digit_str) == 8:
                        try:
                            day = digit_str[:2]
                            month = digit_str[2:4]
                            year = digit_str[4:]
                            if 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
                                return f"{year}/{month}/{day}"
                        except:
                            pass
            
            return date_str
        
        # 应用处理函数
        df['结算时间'] = df[date_column].apply(process_date)
        
        # 提取结算周期（年月格式：YYYYMM）
        def extract_period(date_str):
            """从结算时间提取结算周期"""
            if not date_str or len(date_str) < 7:
                return ''
            # 格式：YYYY/MM/DD -> YYYYMM
            try:
                parts = date_str.split('/')
                if len(parts) == 3:
                    return f"{parts[0]}{parts[1]}"
            except:
                pass
            return ''
        
        df['结算周期'] = df['结算时间'].apply(extract_period)
        
        logger.info(f"结算时间处理完成，结算周期: {df['结算周期'].unique()[:5].tolist()}")
        
        return df
    
    def _detect_currency_columns(self, df: pd.DataFrame) -> List[str]:
        """
        自动检测货币列
        
        Args:
            df: DataFrame
            
        Returns:
            检测到的货币列名列表
        """
        detected = []
        
        for col in df.columns:
            col_lower = str(col).lower()
            
            # 检查列名关键词
            if any(kw in col_lower for kw in self.CURRENCY_COLUMN_KEYWORDS):
                detected.append(col)
                continue
            
            # 检查数据类型
            if df[col].dtype == object:
                sample = df[col].dropna().head(10)
                if len(sample) > 0:
                    # 检查是否包含货币相关字符
                    sample_str = ' '.join([str(v) for v in sample])
                    currency_chars = ['$', '€', '£', '¥', '₹', 'R$', '¥']
                    
                    if any(c in sample_str for c in currency_chars):
                        detected.append(col)
                    # 检查是否包含数字和括号（负数格式）
                    elif sample_str.count('(') > 2:
                        detected.append(col)
        
        return detected
    
    def _convert_column_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        转换列数据类型
        
        Args:
            df: DataFrame
            
        Returns:
            转换后的DataFrame
        """
        # 转换数值列
        numeric_keywords = ['数量', '数量', 'qty']
        
        for col in df.columns:
            col_lower = str(col).lower()
            
            if any(kw in col_lower for kw in numeric_keywords):
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
                except:
                    pass
        
        return df
    
    def fill_null_values(
        self, 
        df: pd.DataFrame,
        strategy: Dict[str, Union[any, str]]
    ) -> pd.DataFrame:
        """
        智能填充空值
        
        Args:
            df: 原始DataFrame
            strategy: 填充策略，{列名: 填充值或策略}
                     策略支持: 'mean', 'median', 'mode', 0, 或具体值
            
        Returns:
            填充后的DataFrame
        """
        df = df.copy()
        
        for col, fill_value in strategy.items():
            if col not in df.columns:
                continue
            
            null_count = df[col].isna().sum()
            
            if fill_value == 'mean':
                df[col] = df[col].fillna(df[col].mean())
            elif fill_value == 'median':
                df[col] = df[col].fillna(df[col].median())
            elif fill_value == 'mode':
                mode_val = df[col].mode()
                if len(mode_val) > 0:
                    df[col] = df[col].fillna(mode_val[0])
            else:
                df[col] = df[col].fillna(fill_value)
            
            self._null_converted_count += null_count
        
        return df
    
    def remove_outliers(
        self, 
        df: pd.DataFrame, 
        column: str, 
        method: str = 'iqr',
        threshold: float = 1.5
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        移除异常值
        
        Args:
            df: 原始DataFrame
            column: 需要检查的列
            method: 移除方法 - 'iqr'(四分位距) 或 'zscore'
            threshold: 阈值
            
        Returns:
            (正常数据DataFrame, 异常数据DataFrame)
        """
        if column not in df.columns:
            return df, pd.DataFrame()
        
        if method == 'iqr':
            Q1 = df[column].quantile(0.25)
            Q3 = df[column].quantile(0.75)
            IQR = Q3 - Q1
            
            lower_bound = Q1 - threshold * IQR
            upper_bound = Q3 + threshold * IQR
            
            normal_mask = (df[column] >= lower_bound) & (df[column] <= upper_bound)
        
        elif method == 'zscore':
            mean = df[column].mean()
            std = df[column].std()
            
            z_scores = np.abs((df[column] - mean) / std)
            normal_mask = z_scores < threshold
        
        else:
            normal_mask = pd.Series([True] * len(df))
        
        normal_df = df[normal_mask].copy()
        outlier_df = df[~normal_mask].copy()
        
        logger.info(f"检测到 {len(outlier_df)} 个异常值")
        
        return normal_df, outlier_df
    
    def get_cleaning_statistics(self) -> Dict:
        """
        获取清洗统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'cleaned_dataframes': self._cleaned_count,
            'null_converted': self._null_converted_count,
            'formats_fixed': self._format_fixed_count,
        }
    
    def reset_statistics(self) -> None:
        """重置统计信息"""
        self._cleaned_count = 0
        self._null_converted_count = 0
        self._format_fixed_count = 0


# 类型别名
Tuple = tuple


