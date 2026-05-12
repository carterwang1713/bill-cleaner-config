"""
数据加载引擎
负责从多种格式加载亚马逊账单数据
"""
import pandas as pd
from typing import Dict, List, Optional, Callable
from pathlib import Path
from loguru import logger
import re

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import BUSINESS_CONFIG


class DataLoader:
    """
    亚马逊账单数据加载器
    
    功能：
    1. 从目录批量加载多站点账单
    2. 支持CSV和Excel格式
    3. 自动识别站点和月份
    4. 合并多文件数据
    
    使用示例：
        loader = DataLoader()
        data = loader.load_from_directory("/path/to/bills")
        df = loader.load_single_file("/path/to/bills/202401US.csv")
    """
    
    def __init__(self):
        """初始化数据加载器"""
        self._supported_formats = BUSINESS_CONFIG.supported_formats
        self._skip_rows = BUSINESS_CONFIG.skip_header_rows
        self._progress_callback: Optional[Callable] = None
        self._loaded_count = 0
        self._total_count = 0
        
        logger.info("数据加载引擎初始化完成")
    
    def set_progress_callback(self, callback: Callable[[str, int, int], None]) -> None:
        """
        设置进度回调函数
        
        Args:
            callback: 回调函数，签名: (message, current, total)
        """
        self._progress_callback = callback
    
    def _report_progress(self, message: str) -> None:
        """报告进度"""
        if self._progress_callback:
            self._loaded_count += 1
            self._progress_callback(message, self._loaded_count, self._total_count)
    
    def load_from_directory(
        self, 
        dir_path: str, 
        recursive: bool = True,
        merge: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        从目录加载多站点账单数据
        
        Args:
            dir_path: 目录路径
            recursive: 是否递归扫描子目录
            merge: 是否合并相同站点的数据
            
        Returns:
            {国家代码: DataFrame} 的字典
        """
        dir_path = Path(dir_path)
        
        if not dir_path.exists():
            logger.error(f"目录不存在: {dir_path}")
            return {}
        
        # 收集所有文件
        all_files = []
        pattern = "**/*" if recursive else "*"
        
        for ext in self._supported_formats:
            all_files.extend(list(dir_path.glob(f"{pattern}{ext}")))
        
        self._total_count = len(all_files)
        self._loaded_count = 0
        
        logger.info(f"开始加载 {self._total_count} 个文件")
        
        # 按站点分组加载
        data_by_country: Dict[str, List[pd.DataFrame]] = {}
        
        for file_path in all_files:
            try:
                df = self._load_file_internal(file_path)
                
                if df is None or df.empty:
                    self._report_progress(f"跳过空文件: {file_path.name}")
                    continue
                
                # 提取国家代码
                country = self._extract_country(file_path)
                
                if country not in data_by_country:
                    data_by_country[country] = []
                data_by_country[country].append(df)
                
                self._report_progress(f"已加载: {file_path.name}")
                
            except Exception as e:
                logger.error(f"加载文件失败 {file_path}: {e}")
                self._report_progress(f"加载失败: {file_path.name}")
        
        # 合并数据
        if merge:
            result = {}
            for country, dfs in data_by_country.items():
                if len(dfs) == 1:
                    result[country] = dfs[0]
                else:
                    logger.info(f"合并 {country} 站点的 {len(dfs)} 个文件")
                    result[country] = pd.concat(dfs, ignore_index=True)
                    # 去除可能的重复行
                    result[country] = result[country].drop_duplicates()
        else:
            # 不合并，返回第一个文件
            result = {country: dfs[0] for country, dfs in data_by_country.items()}
        
        logger.info(f"加载完成，共 {len(result)} 个站点")
        return result
    
    def load_single_file(self, file_path: str, skip_rows: int = None, encoding: str = None) -> Optional[pd.DataFrame]:
        """
        加载单个账单文件
        
        Args:
            file_path: 文件路径
            skip_rows: 跳过行数（默认使用配置值）
            encoding: 文件编码（默认自动检测）
            
        Returns:
            DataFrame，失败返回None
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"文件不存在: {file_path}")
            return None
        
        # 使用传入值或默认值
        if skip_rows is None:
            skip_rows = self._skip_rows
        
        df = self._load_file_internal(file_path, skip_rows=skip_rows, encoding=encoding)
        
        if df is not None:
            # 检查原始数据中是否已有站点相关列
            site_keywords = ['site de vente', 'marketplace', '站点', 'market', 'サイト', 'verkoopplaats']
            has_site_column = any(
                any(kw in str(col).lower() for kw in site_keywords)
                for col in df.columns
            )
            
            # 添加站点列（如果不存在站点相关列）
            country = self._extract_country(file_path)
            if not has_site_column:
                df['站点'] = country
            
            # 暂时注释掉结算周期，保持简洁
            # # 提取结算周期（如果不存在）
            # period = self._extract_period(file_path)
            # if '结算周期' not in df.columns and 'settlement period' not in str(df.columns).lower():
            #     df['结算周期'] = period
        
        return df
    
    def _load_file_internal(self, file_path: Path, skip_rows: int = None, encoding: str = None) -> Optional[pd.DataFrame]:
        """
        内部方法：加载单个文件
        
        Args:
            file_path: 文件路径
            skip_rows: 跳过行数（如果为None则自动检测）
            encoding: 文件编码
            
        Returns:
            DataFrame
        """
        ext = file_path.suffix.lower()
        
        try:
            if ext == '.csv':
                # 如果指定了编码，优先使用指定编码
                if encoding:
                    encodings_to_try = [encoding]
                else:
                    encodings_to_try = ['utf-8', 'utf-8-sig', 'latin-1', 'gbk']
                
                for enc in encodings_to_try:
                    try:
                        # 如果明确指定了skip_rows，直接使用
                        if skip_rows is not None and skip_rows > 0:
                            df = pd.read_csv(file_path, encoding=enc, skiprows=skip_rows, low_memory=False)
                        else:
                            # 智能检测列名行
                            header_row = self._smart_detect_header_row(file_path, enc)
                            
                            if header_row >= 0:
                                logger.info(f"智能检测到列名行: 第{header_row + 1}行")
                                df = pd.read_csv(file_path, encoding=enc, skiprows=header_row, low_memory=False)
                            else:
                                # 检测失败，使用默认值
                                df = pd.read_csv(file_path, encoding=enc, skiprows=self._skip_rows, low_memory=False)
                        
                        # 验证数据有效性
                        if df.shape[1] >= 3:
                            # 提取货币信息
                            currency = self._extract_currency(file_path, enc)
                            if currency:
                                df.attrs['currency'] = currency
                            break
                    except UnicodeDecodeError:
                        continue
                else:
                    # 所有编码都失败，使用latin-1
                    df = pd.read_csv(file_path, encoding='latin-1', low_memory=False)
                    
            elif ext in ['.xlsx', '.xls']:
                # Excel文件
                # 先检查是否有多个sheet
                xl = pd.ExcelFile(file_path, engine='openpyxl' if ext == '.xlsx' else 'xlrd')
                sheet_names = xl.sheet_names
                
                if len(sheet_names) > 1:
                    # 读取所有sheet并合并
                    dfs = []
                    for sheet in sheet_names:
                        try:
                            df_sheet = pd.read_excel(file_path, sheet_name=sheet, engine='openpyxl')
                            if df_sheet is not None and not df_sheet.empty:
                                dfs.append(df_sheet)
                        except Exception as e:
                            logger.warning(f"读取sheet {sheet} 失败: {e}")
                    
                    if dfs:
                        df = pd.concat(dfs, ignore_index=True)
                    else:
                        return None
                else:
                    # 单个sheet，跳过前几行元数据
                    df = pd.read_excel(file_path, engine='openpyxl', skiprows=self._skip_rows)
            else:
                logger.error(f"不支持的文件格式: {ext}")
                return None
            
            # 清理空行和空列
            df = df.dropna(how='all')
            df = df.dropna(axis=1, how='all')
            
            return df
            
        except Exception as e:
            logger.error(f"加载文件失败 {file_path}: {e}")
            raise
    
    def _smart_detect_header_row(self, file_path: Path, encoding: str) -> int:
        """
        智能检测列名行
        
        逻辑：
        1. 逐行读取前20行
        2. 检测每行的字段数
        3. 当字段数从少量（1-3个）突然变成大量（10+个）时，该行就是列名行
        
        Args:
            file_path: 文件路径
            encoding: 文件编码
            
        Returns:
            列名所在行索引（从0开始），检测失败返回-1
        """
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                lines = [f.readline() for _ in range(20)]  # 读取前20行
            
            prev_field_count = 0
            for idx, line in enumerate(lines):
                if not line.strip():
                    continue
                
                # 使用CSV解析器准确计算字段数
                import csv
                from io import StringIO
                reader = csv.reader(StringIO(line))
                fields = next(reader, [])
                field_count = len(fields)
                
                logger.debug(f"第{idx + 1}行: {field_count}个字段")
                
                # 检测字段数突变
                if prev_field_count > 0 and prev_field_count <= 3 and field_count >= 10:
                    logger.info(f"检测到列名行: 第{idx + 1}行（字段数从{prev_field_count}变为{field_count}）")
                    return idx
                
                prev_field_count = field_count
            
            # 如果没有检测到突变，尝试关键词检测
            for idx, line in enumerate(lines):
                line_lower = line.lower()
                header_keywords = ['date', 'order', 'settlement', 'sku', 'type', 'description', 'quantity', 'amount']
                matches = sum(1 for kw in header_keywords if kw in line_lower)
                
                if matches >= 3:
                    logger.info(f"通过关键词检测到列名行: 第{idx + 1}行")
                    return idx
            
            logger.warning("未检测到列名行，使用默认值")
            return self._skip_rows
            
        except Exception as e:
            logger.warning(f"智能检测列名行失败: {e}，使用默认值")
            return self._skip_rows
    
    def _extract_currency(self, file_path: Path, encoding: str) -> Optional[str]:
        """
        从第2行提取货币信息
        
        Args:
            file_path: 文件路径
            encoding: 文件编码
            
        Returns:
            货币代码（如 'EUR', 'USD', 'GBP'），未找到返回None
        """
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                lines = [f.readline() for _ in range(5)]  # 读取前5行
            
            # 检查第2行（索引1）
            if len(lines) >= 2:
                line2 = lines[1].upper()
                
                # 货币关键词映射
                currency_map = {
                    'EUR': ['EUR', 'EURO', '欧元'],
                    'USD': ['USD', 'DOLLAR', '美元'],
                    'GBP': ['GBP', 'POUND', '英镑'],
                    'JPY': ['JPY', 'YEN', '日元'],
                    'CAD': ['CAD', 'CANADIAN', '加元'],
                    'CNY': ['CNY', 'RMB', '人民币'],
                }
                
                for currency, keywords in currency_map.items():
                    if any(kw in line2 for kw in keywords):
                        logger.info(f"从第2行检测到货币: {currency}")
                        return currency
            
            # 扩展到前5行搜索
            for line in lines:
                line_upper = line.upper()
                for currency, keywords in currency_map.items():
                    if any(kw in line_upper for kw in keywords):
                        logger.info(f"检测到货币: {currency}")
                        return currency
            
            return None
            
        except Exception as e:
            logger.warning(f"提取货币信息失败: {e}")
            return None
    
    def _find_header_row(self, df_raw: pd.DataFrame) -> int:
        """
        查找包含列名的行
        
        Args:
            df_raw: 原始DataFrame（前10行）
            
        Returns:
            列名所在行索引
        """
        # 常见的列名关键词
        header_keywords = ['order', 'settlement', 'transaction', 'amount', 'sku', 'asin', 'quantity']
        
        for idx, row in df_raw.iterrows():
            row_str = ' '.join([str(v).lower() for v in row.values if pd.notna(v)])
            matches = sum(1 for kw in header_keywords if kw in row_str)
            
            if matches >= 2:
                return idx
        
        return 0
    
    def _extract_country(self, file_path: Path) -> str:
        """
        从文件路径提取国家代码
        
        Args:
            file_path: 文件路径
            
        Returns:
            国家代码
        """
        filename = file_path.stem
        
        # 从文件名提取
        if len(filename) >= 8:
            potential = filename[6:8].upper()
            if potential in BUSINESS_CONFIG.supported_countries:
                return potential
        
        # 从目录名提取
        parent = file_path.parent.name.upper()
        if parent in BUSINESS_CONFIG.supported_countries:
            return parent
        
        # 从完整路径提取
        path_str = str(file_path).upper()
        for country in BUSINESS_CONFIG.supported_countries:
            if country in path_str:
                return country
        
        return "UNKNOWN"
    
    def _extract_period(self, file_path: Path) -> str:
        """
        从文件路径提取结算周期
        
        Args:
            file_path: 文件路径
            
        Returns:
            结算周期（YYYY-MM格式）
        """
        filename = file_path.stem
        
        # 尝试从文件名提取
        pattern = r'(\d{4})[-_]?(\d{2})'
        match = re.search(pattern, filename)
        
        if match:
            year, month = match.groups()
            return f"{year}-{month}"
        
        return ""
    
    def merge_dataframes(self, data_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        合并多个DataFrame
        
        Args:
            data_dict: {站点: DataFrame} 字典
            
        Returns:
            合并后的DataFrame
        """
        if not data_dict:
            return pd.DataFrame()
        
        dfs = []
        
        for country, df in data_dict.items():
            df = df.copy()
            df['站点'] = country
            dfs.append(df)
        
        merged = pd.concat(dfs, ignore_index=True)
        logger.info(f"合并完成，共 {len(merged)} 行数据")
        
        return merged
    
    def get_file_info(self, file_path: str) -> Dict:
        """
        获取文件信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件信息字典
        """
        path = Path(file_path)
        
        info = {
            'name': path.name,
            'size': path.stat().st_size if path.exists() else 0,
            'extension': path.suffix.lower(),
            'country': self._extract_country(path),
            'period': self._extract_period(path),
            'exists': path.exists(),
        }
        
        return info


# 导出类
__all__ = ['DataLoader']
