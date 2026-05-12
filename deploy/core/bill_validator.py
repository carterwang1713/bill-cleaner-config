"""
账单验证引擎
负责验证亚马逊账单文件的合法性、规范性和完整性
"""
import pandas as pd
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import re
from datetime import datetime
from loguru import logger

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import BUSINESS_CONFIG


class ValidationResult:
    """验证结果"""
    
    def __init__(self):
        self.is_valid: bool = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.suggestions: List[str] = []
    
    def add_error(self, message: str) -> None:
        """添加错误"""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str) -> None:
        """添加警告"""
        self.warnings.append(message)
    
    def add_suggestion(self, message: str) -> None:
        """添加建议"""
        self.suggestions.append(message)
    
    def merge(self, other: 'ValidationResult') -> None:
        """合并另一个验证结果"""
        if not other.is_valid:
            self.is_valid = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.suggestions.extend(other.suggestions)
    
    def __str__(self) -> str:
        lines = []
        if self.errors:
            lines.append(f"错误 ({len(self.errors)}):")
            lines.extend([f"  - {e}" for e in self.errors])
        if self.warnings:
            lines.append(f"警告 ({len(self.warnings)}):")
            lines.extend([f"  - {w}" for w in self.warnings])
        if self.suggestions:
            lines.append(f"建议 ({len(self.suggestions)}):")
            lines.extend([f"  - {s}" for s in self.suggestions])
        if self.is_valid and not self.warnings:
            lines.append("✓ 验证通过")
        return "\n".join(lines)


class BillValidator:
    """
    账单验证引擎
    
    功能：
    1. 验证文件名格式（年月+国家代码前缀）
    2. 验证文件目录结构
    3. 验证数据列完整性
    4. 检测数据异常
    
    使用示例：
        validator = BillValidator()
        result = validator.validate_directory("/path/to/bills")
    """
    
    # 必需列名（不同站点可能略有不同）
    REQUIRED_COLUMNS = [
        "settlement-id", "order-id", "transaction-type",
        "amount-type", "amount", "quantity"
    ]
    
    # 文件名前缀正则表达式
    FILENAME_PATTERN = re.compile(r'^(\d{4})(\d{2})([A-Z]{2})$')
    
    # 国家代码集合
    VALID_COUNTRY_CODES = set(BUSINESS_CONFIG.supported_countries)
    
    def __init__(self):
        """初始化验证器"""
        self._validation_history: List[ValidationResult] = []
        logger.info("账单验证引擎初始化完成")
    
    def validate_filename(self, filename: str) -> ValidationResult:
        """
        验证文件名格式
        
        Args:
            filename: 文件名（不含路径）
            
        Returns:
            验证结果
        """
        result = ValidationResult()
        
        # 去除路径
        filename = Path(filename).name
        
        # 检查扩展名
        ext = Path(filename).suffix.lower()
        if ext not in BUSINESS_CONFIG.supported_formats:
            result.add_error(f"不支持的文件格式: {ext}，支持格式: {BUSINESS_CONFIG.supported_formats}")
        
        # 提取前缀（去除扩展名后）
        name_without_ext = Path(filename).stem
        if len(name_without_ext) >= 8:
            prefix = name_without_ext[:8]
        else:
            prefix = name_without_ext
        
        # 匹配前缀格式
        match = self.FILENAME_PATTERN.match(prefix)
        if not match:
            result.add_warning(f"文件名格式不符合规范: {filename}")
            result.add_suggestion(f"建议命名格式: YYYYMMCC（如202401US.csv）")
        else:
            year, month, country = match.groups()
            
            # 验证年月合理性
            try:
                year_int = int(year)
                month_int = int(month)
                
                if year_int < 2000 or year_int > 2100:
                    result.add_error(f"年份超出合理范围: {year}")
                
                if month_int < 1 or month_int > 12:
                    result.add_error(f"月份超出合理范围: {month}")
                    
                # 检查是否未来日期
                current_year = datetime.now().year
                if year_int > current_year:
                    result.add_warning(f"文件日期为未来时间: {year}")
                
            except ValueError as e:
                result.add_error(f"日期解析失败: {e}")
            
            # 验证国家代码
            if country not in self.VALID_COUNTRY_CODES:
                result.add_warning(f"未知的国家代码: {country}，支持: {self.VALID_COUNTRY_CODES}")
        
        return result
    
    def validate_file(self, file_path: str, skip_rows: int = None) -> ValidationResult:
        """
        验证单个文件
        
        Args:
            file_path: 文件路径
            skip_rows: 跳过的行数，默认使用配置值
            
        Returns:
            验证结果
        """
        result = ValidationResult()
        file_path = Path(file_path)
        
        # 检查文件存在
        if not file_path.exists():
            result.add_error(f"文件不存在: {file_path}")
            return result
        
        # 验证文件名
        filename_result = self.validate_filename(file_path.name)
        result.merge(filename_result)
        
        if not file_path.exists():
            return result
        
        # 验证文件大小
        file_size = file_path.stat().st_size
        if file_size == 0:
            result.add_error("文件为空")
        elif file_size < 100:
            result.add_warning("文件过小，可能数据不完整")
        
        # 尝试读取文件
        try:
            if skip_rows is None:
                skip_rows = BUSINESS_CONFIG.skip_header_rows
            
            # 根据文件类型选择读取方式
            ext = file_path.suffix.lower()
            if ext == '.csv':
                df = pd.read_csv(file_path, encoding='utf-8', low_memory=False)
            else:
                df = pd.read_excel(file_path, engine='openpyxl', header=None)
                if skip_rows > 0:
                    df = pd.read_excel(file_path, engine='openpyxl', skiprows=skip_rows)
            
            # 验证数据行数
            if len(df) == 0:
                result.add_warning("文件中没有数据行")
            
            # 检查列名
            if df.shape[1] < 3:
                result.add_warning("列数过少，可能不是有效的账单文件")
                
        except Exception as e:
            result.add_error(f"读取文件失败: {e}")
        
        return result
    
    def validate_directory(
        self, 
        dir_path: str, 
        recursive: bool = True,
        validate_files: bool = True
    ) -> Tuple[ValidationResult, Dict[str, List[str]]]:
        """
        验证目录结构
        
        Args:
            dir_path: 目录路径
            recursive: 是否递归扫描子目录
            validate_files: 是否验证每个文件
            
        Returns:
            (整体验证结果, {国家代码: [文件列表]})
        """
        result = ValidationResult()
        files_by_country: Dict[str, List[str]] = {}
        dir_path = Path(dir_path)
        
        if not dir_path.exists():
            result.add_error(f"目录不存在: {dir_path}")
            return result, files_by_country
        
        if not dir_path.is_dir():
            result.add_error(f"路径不是目录: {dir_path}")
            return result, files_by_country
        
        # 扫描文件
        pattern = "**/*" if recursive else "*"
        all_files = list(dir_path.glob(pattern))
        
        csv_files = [f for f in all_files if f.is_file() and f.suffix.lower() == '.csv']
        excel_files = [f for f in all_files if f.is_file() and f.suffix.lower() in ['.xlsx', '.xls']]
        
        logger.info(f"发现文件: CSV={len(csv_files)}, Excel={len(excel_files)}")
        
        # 验证每个CSV文件
        for file_path in csv_files:
            if validate_files:
                file_result = self.validate_file(str(file_path))
                result.merge(file_result)
            
            # 提取国家代码
            country = self._extract_country_from_path(file_path)
            if country:
                if country not in files_by_country:
                    files_by_country[country] = []
                files_by_country[country].append(str(file_path))
        
        # 验证Excel文件
        for file_path in excel_files:
            if validate_files:
                file_result = self.validate_file(str(file_path))
                result.merge(file_result)
            
            country = self._extract_country_from_path(file_path)
            if country:
                if country not in files_by_country:
                    files_by_country[country] = []
                files_by_country[country].append(str(file_path))
        
        # 检查站点覆盖
        if not files_by_country:
            result.add_warning("未找到任何有效的账单文件")
        else:
            logger.info(f"按站点分组: {list(files_by_country.keys())}")
        
        self._validation_history.append(result)
        return result, files_by_country
    
    def _extract_country_from_path(self, file_path: Path) -> Optional[str]:
        """
        从文件路径提取国家代码
        
        Args:
            file_path: 文件路径
            
        Returns:
            国家代码，如果未找到返回None
        """
        # 从文件名提取
        filename = file_path.stem
        if len(filename) >= 8:
            potential_country = filename[6:8].upper()
            if potential_country in self.VALID_COUNTRY_CODES:
                return potential_country
        
        # 从目录名提取
        parent_name = file_path.parent.name.upper()
        if parent_name in self.VALID_COUNTRY_CODES:
            return parent_name
        
        # 扫描路径中的国家代码
        for part in file_path.parts:
            part_upper = part.upper()
            if part_upper in self.VALID_COUNTRY_CODES:
                return part_upper
        
        return None
    
    def validate_dataframe(self, df: pd.DataFrame, required_cols: List[str] = None) -> ValidationResult:
        """
        验证DataFrame数据完整性
        
        Args:
            df: 数据DataFrame
            required_cols: 必需列名列表
            
        Returns:
            验证结果
        """
        result = ValidationResult()
        
        if df is None or df.empty:
            result.add_error("DataFrame为空")
            return result
        
        # 检查必需列
        if required_cols is None:
            required_cols = self.REQUIRED_COLUMNS
        
        existing_cols = set(df.columns.str.lower())
        missing_cols = []
        
        for col in required_cols:
            col_lower = col.lower()
            if col_lower not in existing_cols:
                # 尝试模糊匹配
                matched = False
                for existing in existing_cols:
                    if col_lower in existing or existing in col_lower:
                        matched = True
                        break
                if not matched:
                    missing_cols.append(col)
        
        if missing_cols:
            result.add_warning(f"缺少建议列: {missing_cols}")
        
        # 检查空值
        for col in df.columns:
            null_count = df[col].isna().sum()
            null_ratio = null_count / len(df) if len(df) > 0 else 0
            
            if null_ratio > 0.8:
                result.add_warning(f"列 '{col}' 空值比例过高: {null_ratio:.1%}")
            elif null_ratio > 0.5:
                result.add_suggestion(f"列 '{col}' 空值较多: {null_ratio:.1%}")
        
        return result
    
    @property
    def validation_history(self) -> List[ValidationResult]:
        """获取验证历史"""
        return self._validation_history.copy()
    
    def generate_report(self, result: ValidationResult) -> str:
        """
        生成验证报告
        
        Args:
            result: 验证结果
            
        Returns:
            格式化的报告字符串
        """
        return str(result)


# 导出类
__all__ = ['BillValidator', 'ValidationResult']
