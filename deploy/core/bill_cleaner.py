"""
亚马逊账单清洗引擎 - 完整版
确保所有映射表都被正确使用
"""
import pandas as pd
import numpy as np
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from loguru import logger


class BillCleaner:
    """
    亚马逊账单清洗引擎
    
    映射表使用清单：
    1. column_name_full_mapping.csv - 列名翻译（多语言→中文）
    2. matching_helper_to_chinese.csv - 匹配辅助列→中文意思
    3. 规则表1_无需关注description的type列表.csv - 匹配辅助列生成规则
    4. 规则表2_需关注部分description的type规则.csv - 匹配辅助列生成规则
    5. 规则表3_需关注全部description的type示例.csv - 参考示例
    6. product_mapping.csv - SKU→产品ID映射
    7. 汇率表_各币种兑美元.csv - 汇率转换
    8. performance_dimension_mapping.csv - 绩效维度和序列码映射
    """
    
    def __init__(self, mappings_dir: Path, user_data_dir: Path = None):
        """
        初始化清洗引擎
        
        Args:
            mappings_dir: 映射表目录路径（GitHub基准汇率所在目录）
            user_data_dir: 用户数据目录路径（本地覆盖汇率所在目录），可选
        """
        self.mappings_dir = Path(mappings_dir)
        self.user_data_dir = Path(user_data_dir) if user_data_dir else None
        
        # 初始化映射字典
        self.column_name_mapping: Dict[str, str] = {}  # 列名映射
        self.chinese_meaning_mapping: Dict[str, str] = {}  # 中文意思映射
        self.no_desc_types: set = set()  # 规则表1：无需关注description的type（改为set加速）
        self.partial_desc_rules: List[Dict] = []  # 规则表2：部分description规则
        self._partial_rules_preprocessed: List[Dict] = []  # 预处理后的规则（包含提取的关键词）
        self.exchange_rates: Dict[str, float] = {}  # 汇率表
        self.exchange_rate_sources: Dict[str, str] = {}  # 汇率来源标记: 'github' 或 'local'
        self.performance_mapping: Dict[str, Dict] = {}  # 绩效维度映射
        
        # 加载所有映射表
        self._load_all_mappings()
        
        logger.info("账单清洗引擎初始化完成")
    
    def _load_all_mappings(self):
        """加载所有映射表"""
        # 1. 加载列名映射（所有语言）
        self._load_column_name_mapping()
        
        # 2. 加载中文意思映射
        self._load_chinese_meaning_mapping()
        
        # 3. 加载规则表1
        self._load_no_desc_types()
        
        # 4. 加载规则表2
        self._load_partial_desc_rules()
        
        # 5. 预处理规则表2（提取关键词加速向量化）
        self._preprocess_partial_rules()
        
        # 6. 加载汇率表
        self._load_exchange_rates()
        
        # 7. 加载绩效维度映射表
        self._load_performance_mapping()
        
        logger.info(f"映射表加载完成: 列名{len(self.column_name_mapping)}条, "
                   f"中文意思{len(self.chinese_meaning_mapping)}条, "
                   f"规则1:{len(self.no_desc_types)}条, "
                   f"规则2:{len(self.partial_desc_rules)}条, "
                   f"绩效维度{len(self.performance_mapping)}条")
    
    def _load_column_name_mapping(self):
        """加载列名映射表（从CSV读取所有语言）- 向量化版本"""
        file_path = self.mappings_dir / "column_name_full_mapping.csv"
        if not file_path.exists():
            logger.warning(f"列名映射表不存在: {file_path}")
            return
        
        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            # 向量化构建：原始列名 -> 中文意思 的映射
            df['原始列名'] = df['原始列名'].astype(str).str.strip().apply(self._normalize_text)
            df['中文意思'] = df['中文意思'].astype(str).str.strip()
            # 过滤空值后用 dict + zip 构建
            valid_mask = (df['原始列名'] != '') & (df['中文意思'] != '') & (df['原始列名'] != 'nan') & (df['中文意思'] != 'nan')
            self.column_name_mapping = dict(zip(df.loc[valid_mask, '原始列名'], df.loc[valid_mask, '中文意思']))
            
            logger.info(f"加载列名映射: {len(self.column_name_mapping)} 条")
        except Exception as e:
            logger.error(f"加载列名映射表失败: {e}")
    
    def _load_chinese_meaning_mapping(self):
        """加载中文意思映射表 - 向量化版本"""
        file_path = self.mappings_dir / "matching_helper_to_chinese.csv"
        if not file_path.exists():
            logger.warning(f"中文意思映射表不存在: {file_path}")
            return
        
        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            # 向量化构建：匹配辅助列 -> 中文意思 的映射
            df['匹配辅助列'] = df['匹配辅助列'].astype(str).str.strip()
            df['中文意思'] = df['中文意思'].astype(str).str.strip()
            valid_mask = (df['匹配辅助列'] != '') & (df['中文意思'] != '') & (df['匹配辅助列'] != 'nan') & (df['中文意思'] != 'nan')
            # 统一转小写，避免大小写不一致导致匹配失败
            df.loc[valid_mask, '匹配辅助列'] = df.loc[valid_mask, '匹配辅助列'].str.lower()
            self.chinese_meaning_mapping = dict(zip(df.loc[valid_mask, '匹配辅助列'], df.loc[valid_mask, '中文意思']))
            
            logger.info(f"加载中文意思映射: {len(self.chinese_meaning_mapping)} 条")
        except Exception as e:
            logger.error(f"加载中文意思映射表失败: {e}")
    
    def _load_no_desc_types(self):
        """加载规则表1：无需关注description的type列表 - 向量化版本"""
        file_path = self.mappings_dir / "规则表1_无需关注description的type列表.csv"
        if not file_path.exists():
            logger.warning(f"规则表1不存在: {file_path}")
            return
        
        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            # 向量化获取所有type（小写），转为set
            df['type'] = df['type'].astype(str).str.strip().str.lower()
            valid_mask = (df['type'] != '') & (df['type'] != 'nan')
            self.no_desc_types = set(df.loc[valid_mask, 'type'].tolist())
            
            logger.info(f"加载规则表1: {len(self.no_desc_types)} 条")
        except Exception as e:
            logger.error(f"加载规则表1失败: {e}")
    
    def _load_partial_desc_rules(self):
        """加载规则表2：需关注部分description的type规则 - 向量化版本"""
        file_path = self.mappings_dir / "规则表2_需关注部分description的type规则.csv"
        if not file_path.exists():
            logger.warning(f"规则表2不存在: {file_path}")
            return
        
        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            # 向量化处理
            for _, row in df.iterrows():
                rule = {
                    'type_condition': str(row['type条件']).strip(),
                    'desc_condition': str(row['description条件']).strip(),
                    'matching_helper': str(row['匹配辅助列']).strip(),
                    'description': str(row['说明']).strip(),
                    'priority': int(row['优先级']) if pd.notna(row.get('优先级')) else 999
                }
                self.partial_desc_rules.append(rule)
            
            # 按优先级排序
            self.partial_desc_rules.sort(key=lambda x: x['priority'])
            logger.info(f"加载规则表2: {len(self.partial_desc_rules)} 条")
        except Exception as e:
            logger.error(f"加载规则表2失败: {e}")
    
    def _preprocess_partial_rules(self):
        """
        预处理规则表2，提取type_condition和desc_condition中的关键词
        用于向量化匹配加速
        """
        self._partial_rules_preprocessed = []
        for rule in self.partial_desc_rules:
            type_cond = rule['type_condition'].lower()
            desc_cond = rule['desc_condition'].lower()
            
            # 处理type_condition
            type_match_type = 'any'  # 默认任意
            type_keyword = ''
            type_exact = ''
            if type_cond == '任意':
                type_match_type = 'any'
            elif '包含' in type_cond:
                type_keyword = type_cond.replace('包含', '').strip()
                type_match_type = 'contains'
            else:
                type_exact = type_cond
                type_match_type = 'exact'
            
            # 处理desc_condition
            desc_match_type = 'any'
            desc_keyword = ''
            desc_exact = ''
            if desc_cond == '任意':
                desc_match_type = 'any'
            elif '包含' in desc_cond:
                desc_keyword = desc_cond.replace('包含', '').strip()
                desc_match_type = 'contains'
            else:
                desc_exact = desc_cond
                desc_match_type = 'exact'
            
            self._partial_rules_preprocessed.append({
                'type_match_type': type_match_type,
                'type_keyword': type_keyword,
                'type_exact': type_exact,
                'desc_match_type': desc_match_type,
                'desc_keyword': desc_keyword,
                'desc_exact': desc_exact,
                'matching_helper': rule['matching_helper'],
                'priority': rule['priority']
            })
        
        logger.info(f"预处理规则表2完成: {len(self._partial_rules_preprocessed)} 条")
    
    def _load_exchange_rates(self):
        """加载汇率表（支持本地覆盖）- 向量化版本
        
        加载顺序：
        1. 先加载GitHub基准汇率
        2. 再加载本地覆盖汇率（同名key会被覆盖）
        """
        # 1. 加载GitHub基准汇率
        github_file = self.mappings_dir / "汇率表_各币种兑美元.csv"
        if not github_file.exists():
            logger.warning(f"汇率表不存在: {github_file}")
        else:
            try:
                df = pd.read_csv(github_file, encoding='utf-8-sig')
                # 向量化构建汇率字典
                df['币种'] = df['币种'].astype(str).str.strip()
                df['结算周期'] = df['结算周期'].astype(str).str.strip()
                keys = df['币种'] + '_' + df['结算周期']
                rates = df['汇率(原币->USD)'].astype(float)
                for key, rate in zip(keys, rates):
                    self.exchange_rates[key] = rate
                    self.exchange_rate_sources[key] = 'github'
                
                logger.info(f"加载GitHub基准汇率: {sum(1 for v in self.exchange_rate_sources.values() if v == 'github')} 条")
            except Exception as e:
                logger.error(f"加载GitHub汇率表失败: {e}")
        
        # 2. 加载本地覆盖汇率（优先级更高）
        if self.user_data_dir:
            local_file = self.user_data_dir / "local_exchange_rate.csv"
            if local_file.exists():
                try:
                    df = pd.read_csv(local_file, encoding='utf-8-sig')
                    # 向量化处理
                    df['币种'] = df['币种'].astype(str).str.strip()
                    df['结算周期'] = df['结算周期'].astype(str).str.strip()
                    keys = df['币种'] + '_' + df['结算周期']
                    rates = df['汇率(原币->USD)'].astype(float)
                    for key, rate in zip(keys, rates):
                        self.exchange_rates[key] = rate
                        self.exchange_rate_sources[key] = 'local'
                    
                    local_count = sum(1 for v in self.exchange_rate_sources.values() if v == 'local')
                    logger.info(f"加载本地覆盖汇率: {local_count} 条")
                except Exception as e:
                    logger.error(f"加载本地汇率表失败: {e}")
            else:
                logger.info("未发现本地汇率覆盖文件")
        
        logger.info(f"汇率表加载完成: 共 {len(self.exchange_rates)} 条")
    
    def _load_performance_mapping(self):
        """加载绩效维度映射表 - 向量化版本"""
        file_path = self.mappings_dir / "performance_dimension_mapping.csv"
        if not file_path.exists():
            logger.warning(f"绩效维度映射表不存在: {file_path}")
            return
        
        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig')
            # 向量化构建映射字典
            df['站点'] = df['站点'].astype(str).str.strip()
            df['二维匹配数据列-1'] = df['二维匹配数据列-1'].astype(str).str.strip()
            df['二维匹配数据列-2'] = df['二维匹配数据列-2'].astype(str).str.strip()
            df['账单字段序列'] = df['账单字段序列'].astype(str).str.strip()
            df['维度'] = df['维度'].astype(str).str.strip()
            df['绩效表对应维度'] = df['绩效表对应维度'].fillna('').astype(str).str.strip()
            
            # key格式: 站点_中文意思_金额类型
            keys = df['站点'] + '_' + df['二维匹配数据列-1'] + '_' + df['二维匹配数据列-2']
            
            for key, serial, dim_type, perf_dim in zip(keys, df['账单字段序列'], df['维度'], df['绩效表对应维度']):
                self.performance_mapping[key] = {
                    '账单字段序列码': serial,
                    '维度类型': dim_type,
                    '绩效表对应维度': perf_dim
                }
            
            logger.info(f"加载绩效维度映射: {len(self.performance_mapping)} 条")
        except Exception as e:
            logger.error(f"加载绩效维度映射表失败: {e}")
    
    def detect_header_row(self, file_path: str) -> int:
        """
        智能检测表头行：取非空字段最多的那一行
        
        Args:
            file_path: CSV文件路径
            
        Returns:
            表头所在行号（0-based）
        """
        import csv
        
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        
        max_non_empty = 0
        header_row = 0
        
        for i, line in enumerate(lines):
            # 解析CSV行
            try:
                fields = list(csv.reader([line]))[0]
                # 统计非空字段数
                non_empty_count = sum(1 for f in fields if f.strip())
                
                if non_empty_count > max_non_empty:
                    max_non_empty = non_empty_count
                    header_row = i
            except:
                continue
        
        if max_non_empty > 0:
            logger.info(f"检测到表头在第 {header_row + 1} 行（非空字段数: {max_non_empty}）")
        else:
            logger.warning("未检测到有效表头，使用第1行")
        
        return header_row
    
    @staticmethod
    def _normalize_text(text: str) -> str:
        """标准化文本：将排版引号等Unicode字符替换为ASCII等价字符"""
        text = text.replace('\u2019', "'")  # RIGHT SINGLE QUOTATION MARK
        text = text.replace('\u2018', "'")  # LEFT SINGLE QUOTATION MARK
        text = text.replace('\u201c', '"')  # LEFT DOUBLE QUOTATION MARK
        text = text.replace('\u201d', '"')  # RIGHT DOUBLE QUOTATION MARK
        text = text.replace('\u00a0', ' ')  # NO-BREAK SPACE
        return text

    def translate_column_names(self, df: pd.DataFrame) -> tuple:
        """
        翻译列名（使用 column_name_full_mapping.csv）
        
        Args:
            df: 原始DataFrame
            
        Returns:
            (列名翻译后的DataFrame, 未翻译的列名列表)
        """
        new_columns = []
        untranslated = []
        
        for col in df.columns:
            col_str = self._normalize_text(str(col).strip())
            if col_str in self.column_name_mapping:
                new_columns.append(self.column_name_mapping[col_str])
            else:
                new_columns.append(col_str)
                if col_str and not col_str.startswith('Unnamed'):
                    untranslated.append(col_str)
        
        df.columns = new_columns
        
        if untranslated:
            logger.warning(f"未翻译的列名: {untranslated[:10]}...")
        
        return df, untranslated
    
    def create_matching_helper(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        创建匹配辅助列（使用规则表1和规则表2）- 向量化版本
        
        规则逻辑：
        1. 如果type在规则表1中，匹配辅助列 = type
        2. 如果匹配规则表2的条件，匹配辅助列 = 规则表2的匹配辅助列
        3. 否则，匹配辅助列 = type/description
        
        Args:
            df: DataFrame
            
        Returns:
            添加了匹配辅助列的DataFrame
        """
        import time
        start_time = time.time()
        df = df.copy()
        
        # 查找结算类型列和订单描述列
        type_col = self._find_column(df, ['结算类型', 'Transaction Type', 'type', 'Type', 'Typ'])
        desc_col = self._find_column(df, ['订单描述', 'Item Description', 'description', 'Description', 'Beschreibung'])
        
        if not type_col:
            logger.warning("未找到结算类型列")
            df['匹配辅助列'] = ''
            return df
        
        logger.info(f"create_matching_helper 向量化优化开始, 行数: {len(df)}")
        
        # 初始化匹配辅助列为空
        df['匹配辅助列'] = ''
        
        # 提取 type 和 description 列（转为小写用于匹配）
        # 注意：pandas StringDtype的.astype(str)不会将NaN转为"nan"字符串，需用.fillna('nan')确保NaN转为字符串
        type_series = df[type_col].fillna('nan').astype(str).str.strip()
        type_lower = type_series.str.lower()
        desc_series = df[desc_col].fillna('nan').astype(str).str.strip() if desc_col else pd.Series([''] * len(df), index=df.index)
        desc_lower = desc_series.str.lower()
        
        # ========== 规则1：检查规则表1（无需关注description）==========
        rule1_mask = type_lower.isin(self.no_desc_types)
        if rule1_mask.any():
            df.loc[rule1_mask, '匹配辅助列'] = type_series[rule1_mask]
            logger.info(f"规则1匹配: {rule1_mask.sum()} 条")
        
        # ========== 规则2：检查规则表2（按优先级顺序）==========
        remaining_mask = df['匹配辅助列'] == ''
        remaining_count = remaining_mask.sum()
        
        if remaining_count > 0 and self._partial_rules_preprocessed:
            # 按优先级顺序应用规则
            for rule_idx, rule in enumerate(self._partial_rules_preprocessed):
                if not remaining_mask.any():
                    break
                    
                current_mask = remaining_mask & ~remaining_mask  # 空mask
                
                # 处理type条件
                if rule['type_match_type'] == 'any':
                    type_match_mask = pd.Series([True] * len(df), index=df.index)
                elif rule['type_match_type'] == 'contains':
                    type_match_mask = type_lower.str.contains(rule['type_keyword'], regex=False, na=False)
                else:  # exact
                    type_match_mask = type_lower == rule['type_exact']
                
                # 处理desc条件
                if rule['desc_match_type'] == 'any':
                    desc_match_mask = pd.Series([True] * len(df), index=df.index)
                elif rule['desc_match_type'] == 'contains':
                    desc_match_mask = desc_lower.str.contains(rule['desc_keyword'], regex=False, na=False)
                else:  # exact
                    desc_match_mask = desc_lower == rule['desc_exact']
                
                # 组合条件：同时满足type和desc条件
                combined_mask = remaining_mask & type_match_mask & desc_match_mask
                
                if combined_mask.any():
                    df.loc[combined_mask, '匹配辅助列'] = rule['matching_helper']
                    remaining_mask = remaining_mask & ~combined_mask
                    logger.info(f"规则2[{rule_idx}] 匹配 '{rule['matching_helper']}': {combined_mask.sum()} 条")
        
        # ========== 规则3：默认规则 type/description =========
        remaining_mask = df['匹配辅助列'] == ''
        if remaining_mask.any():
            # 有description用 type/description，否则用 type
            has_desc = desc_series[remaining_mask] != ''
            mask_with_desc = remaining_mask & (desc_series != '')
            mask_without_desc = remaining_mask & (desc_series == '')
            
            # 细分：有type有desc / 有desc无type / 有type无desc / 都无
            mask_has_type = type_series != ''
            mask_full = mask_with_desc & mask_has_type  # type+desc都有
            mask_desc_only = mask_with_desc & ~mask_has_type  # 只有desc，type为空
            mask_type_only = mask_without_desc & mask_has_type  # 只有type，desc为空
            
            if mask_full.any():
                df.loc[mask_full, '匹配辅助列'] = type_series[mask_full] + '/' + desc_series[mask_full]
            if mask_desc_only.any():
                # type为空时，匹配辅助列直接用description
                df.loc[mask_desc_only, '匹配辅助列'] = desc_series[mask_desc_only]
            if mask_type_only.any():
                df.loc[mask_type_only, '匹配辅助列'] = type_series[mask_type_only]
            logger.info(f"规则3(默认)匹配: {remaining_mask.sum()} 条")
        
        elapsed = time.time() - start_time
        logger.info(f"create_matching_helper 完成, 耗时: {elapsed:.2f}秒")
        
        return df
    
    def match_chinese_meaning(self, df: pd.DataFrame) -> tuple:
        """
        匹配中文意思（使用 matching_helper_to_chinese.csv）- 向量化版本
        
        Args:
            df: 包含匹配辅助列的DataFrame
            
        Returns:
            (添加了中文意思列的DataFrame, 未匹配的详细信息列表)
        """
        import time
        start_time = time.time()
        df = df.copy()
        
        if '匹配辅助列' not in df.columns:
            logger.warning("未找到匹配辅助列")
            df['中文意思'] = ''
            return df, []
        
        logger.info(f"match_chinese_meaning 向量化优化开始, 行数: {len(df)}")
        
        # 向量化：直接用map匹配
        # 注意：pandas StringDtype的.astype(str)不会将NaN转为"nan"字符串，需用.fillna('nan')确保NaN转为字符串
        helper_series = df['匹配辅助列'].fillna('nan').astype(str).str.strip()
        df['中文意思'] = helper_series.str.lower().map(self.chinese_meaning_mapping).fillna('未分类')
        
        # 调试日志：输出未分类的匹配辅助列
        unclassified_mask = df['中文意思'] == '未分类'
        if unclassified_mask.any():
            unclassified_helpers = df.loc[unclassified_mask, '匹配辅助列'].unique()[:10]
            logger.warning(f'未分类的匹配辅助列: {list(unclassified_helpers)}')
        
        # 向量化收集未匹配的样本（包含出现次数）
        unmatched_mask = df['中文意思'] == '未分类'
        unmatched_details = []
        
        if unmatched_mask.any():
            # 获取未匹配的唯一值及其出现次数（按次数降序）
            unmatched_counts = helper_series[unmatched_mask].value_counts()
            
            logger.warning(f"未匹配的匹配辅助列（按出现次数降序）: {unmatched_counts.head(10).to_dict()}")
            
            # 收集未匹配的详细信息（按出现次数降序采样前20个）
            detail_cols = ['站点', '结算类型', '订单描述', '匹配辅助列', '结算金额', 'SKU', '结算周期']
            available_cols = [c for c in detail_cols if c in df.columns]
            
            # 按出现次数降序遍历
            for helper_val, count in unmatched_counts.head(20).items():
                sample_row = df[helper_series == helper_val].iloc[0]
                detail = {'匹配辅助列': helper_val, '出现次数': int(count)}
                for col in available_cols:
                    val = sample_row.get(col, '')
                    if pd.notna(val) and str(val).strip():
                        detail[col] = str(val).strip()
                unmatched_details.append(detail)
        
        elapsed = time.time() - start_time
        logger.info(f"match_chinese_meaning 完成, 耗时: {elapsed:.2f}秒")
        
        return df, unmatched_details
    
    def convert_number_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        转换数字格式（欧洲格式 → 标准格式）- 向量化版本
        
        Args:
            df: DataFrame
            
        Returns:
            数字格式转换后的DataFrame
        """
        import time
        start_time = time.time()
        df = df.copy()
        
        logger.info(f"convert_number_format 向量化优化开始, 列数: {len(df.columns)}")
        
        # 需要转换的数值列关键词
        numeric_keywords = ['金额', '收入', '费用', '佣金', '税', '销量']
        
        # 排除的文本列（虽然包含关键词但不是数值）
        exclude_keywords = ['类型', '日期', '单号', '周期', '时间', '模式', '方式']
        
        # 找出需要转换的数值列
        numeric_cols = []
        for col in df.columns:
            col_str = str(col).lower()
            
            # 先检查是否在排除列表中
            is_excluded = any(ex_kw in col_str for ex_kw in exclude_keywords)
            if is_excluded:
                continue
            
            # 检查是否是数值列
            is_numeric = any(kw in col_str for kw in numeric_keywords)
            if is_numeric:
                numeric_cols.append(col)
        
        logger.info(f"待转换数值列: {numeric_cols}")
        
        # 批量向量化转换
        for col in numeric_cols:
            # 第一步：尝试直接转数值
            numeric_series = pd.to_numeric(df[col], errors='coerce')
            
            # 第二步：找出转换失败的（需要欧洲格式处理的）
            failed_mask = numeric_series.isna() & df[col].notna() & (df[col].astype(str).str.strip() != '') & (df[col].astype(str).str.strip() != '-')
            
            if failed_mask.any():
                # 对失败的进行欧洲格式处理
                european_converted = df.loc[failed_mask, col].apply(self._convert_european_number)
                numeric_series.loc[failed_mask] = european_converted
            
            df[col] = numeric_series.fillna(0.0)
        
        elapsed = time.time() - start_time
        logger.info(f"convert_number_format 完成, 耗时: {elapsed:.2f}秒")
        
        return df
    
    def _convert_european_number(self, value) -> float:
        """转换欧洲数字格式为标准格式"""
        if pd.isna(value) or value == '' or value == '-':
            return 0.0
        
        if isinstance(value, (int, float)):
            return float(value)
        
        value_str = str(value).strip()
        
        # 处理括号表示负数
        is_negative = False
        if '(' in value_str and ')' in value_str:
            is_negative = True
            value_str = value_str.replace('(', '').replace(')', '')
        
        # 替换Unicode负号
        for uni_minus in ['−', '－', '﹣', '⁻', '₋']:
            if uni_minus in value_str:
                is_negative = True
                value_str = value_str.replace(uni_minus, '-')
        
        # 去除货币符号
        value_str = re.sub(r'[$€£¥₹]', '', value_str)
        
        # 去除空格千分位
        value_str = re.sub(r'(\d)\s+(\d)', r'\1\2', value_str)
        
        # 判断格式并转换
        has_comma = ',' in value_str
        has_dot = '.' in value_str
        
        if has_comma and has_dot:
            # 欧式格式: 1.234,56 -> 1234.56
            last_comma = value_str.rfind(',')
            last_dot = value_str.rfind('.')
            if last_dot > last_comma:
                # 美式: 1,234.56
                value_str = value_str.replace(',', '')
            else:
                # 欧式: 1.234,56
                value_str = value_str.replace('.', '').replace(',', '.')
        elif has_comma:
            # 只有逗号，判断是小数点还是千分位
            parts = value_str.split(',')
            if len(parts) == 2 and len(parts[1]) <= 2:
                # 欧式小数: 10,50
                value_str = value_str.replace(',', '.')
            else:
                # 千分位
                value_str = value_str.replace(',', '')
        
        try:
            result = float(value_str)
            return -result if is_negative else result
        except:
            return 0.0
    
    def extract_settlement_period(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        提取结算周期（从结算日期列）
        如果出现多个结算周期，以数量最多的为准（多数决）
        
        Args:
            df: DataFrame
            
        Returns:
            添加了结算周期列的DataFrame
        """
        df = df.copy()
        
        # 查找结算日期列
        date_col = self._find_column(df, ['结算日期', '结算时间', 'date/time', 'Date/Time', 'Datum/Uhrzeit'])
        
        if not date_col:
            logger.warning("未找到结算日期列")
            df['结算周期'] = '未知'
            return df
        
        periods = []
        for val in df[date_col]:
            period = self._extract_period_from_date(str(val))
            periods.append(period)
        
        df['结算周期'] = periods
        
        # 多数决：如果出现多个结算周期，以数量最多的为准
        period_counts = df['结算周期'].value_counts()
        if len(period_counts) > 1 and '未知' not in period_counts.index[:1]:
            # 找出数量最多的结算周期
            majority_period = period_counts.index[0]
            minority_count = period_counts.iloc[1:].sum()
            
            if minority_count > 0:
                logger.info(f"结算周期多数决: {majority_period}({period_counts.iloc[0]}条) 替代其他{minority_count}条")
                df['结算周期'] = majority_period
        
        logger.info(f"结算周期分布: {df['结算周期'].value_counts().to_dict()}")
        
        return df
    
    def _extract_period_from_date(self, date_str: str) -> str:
        """从日期字符串提取年月（YYYYMM格式）"""
        if not date_str or date_str == 'nan':
            return '未知'
        
        # 格式1: 28.02.2026 23:02:42 UTC (欧洲格式)
        match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', date_str)
        if match:
            return f"{match.group(3)}{match.group(2)}"
        
        # 格式2: 2026/02/28 或 2026-02-28
        match = re.search(r'(\d{4})[/\-](\d{2})', date_str)
        if match:
            return f"{match.group(1)}{match.group(2)}"
        
        # 格式3: 28 Feb 2026 (英文月份 - 日在前)
        month_map = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
            'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
            'mär': '03', 'märz': '03', 'mai': '05', 'dez': '12'
        }
        match = re.search(r'(\d{1,2})\s+(\w{3,4})\s+(\d{4})', date_str, re.I)
        if match:
            month_str = match.group(2).lower()[:3]
            month = month_map.get(month_str, '01')
            return f"{match.group(3)}{month}"
        
        # 格式4: Mar 1, 2026 (美区格式 - 月在前)
        match = re.search(r'(\w{3,4})\s+(\d{1,2}),\s+(\d{4})', date_str, re.I)
        if match:
            month_str = match.group(1).lower()[:3]
            month = month_map.get(month_str, '01')
            return f"{match.group(3)}{month}"
        
        return '未知'
    
    def _find_column(self, df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        """查找DataFrame中的列"""
        for candidate in candidates:
            if candidate in df.columns:
                return candidate
        return None
    
    def clean(self, file_path: str, product_mapping_path: Optional[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict]:
        """
        执行完整清洗流程
        
        Args:
            file_path: CSV文件路径
            product_mapping_path: 商品映射表路径（可选）
            
        Returns:
            (二维版本DataFrame, 多维版本DataFrame, 二维美元版本DataFrame, 清洗报告)
        """
        report = {
            'input_file': file_path,
            'steps': [],
            'warnings': [],
            'errors': [],
            'unmatched': {
                'column_names': [],        # 未翻译的列名
                'chinese_meanings': [],    # 未匹配的中文意思
                'exchange_rates': [],      # 未匹配的汇率
                'performance_dimensions': [],  # 未匹配的绩效维度
                'product_skus': []         # 未匹配的商品SKU
            }
        }
        
        try:
            # Step 1: 智能检测表头并加载数据
            logger.info("Step 1: 检测表头并加载数据")
            header_row = self.detect_header_row(file_path)
            df = pd.read_csv(file_path, encoding='utf-8-sig', header=header_row, low_memory=False)
            report['steps'].append(f"加载数据: {len(df)} 行, 表头在第 {header_row + 1} 行")
            
            # Step 1.5: 从文件头部提取币种信息
            currency = self._extract_currency_from_file(file_path)
            if currency:
                df.attrs['currency'] = currency
                logger.info(f"检测到币种: {currency}")
            
            # Step 2: 翻译列名
            logger.info("Step 2: 翻译列名")
            df, untranslated_cols = self.translate_column_names(df)
            report['steps'].append(f"翻译列名: {len(df.columns)} 列")
            if untranslated_cols:
                report['unmatched']['column_names'] = untranslated_cols
                report['warnings'].append(f"⚠️ 未翻译的列名: {untranslated_cols[:10]}")
            
            # Step 3: 数字格式转换
            logger.info("Step 3: 数字格式转换")
            df = self.convert_number_format(df)
            report['steps'].append("数字格式转换完成")
            
            # Step 4: 提取结算周期
            logger.info("Step 4: 提取结算周期")
            df = self.extract_settlement_period(df)
            report['steps'].append(f"结算周期: {df['结算周期'].unique().tolist()}")
            
            # Step 5: 创建匹配辅助列
            logger.info("Step 5: 创建匹配辅助列")
            df = self.create_matching_helper(df)
            report['steps'].append("匹配辅助列创建完成")
            
            # Step 6: 匹配中文意思
            logger.info("Step 6: 匹配中文意思")
            df, unmatched_chinese = self.match_chinese_meaning(df)
            chinese_dist = df['中文意思'].value_counts().to_dict()
            report['steps'].append(f"中文意思分布: {list(chinese_dist.items())[:5]}")
            if unmatched_chinese:
                report['unmatched']['chinese_meanings'] = unmatched_chinese
                report['warnings'].append(f"⚠️ 未匹配的中文意思（匹配辅助列）: {unmatched_chinese[:10]}")
            
            # Step 7: 商品映射（如果提供了映射表）
            unmatched_skus = []
            if product_mapping_path and Path(product_mapping_path).exists():
                logger.info("Step 7: 商品映射")
                df, unmatched_skus = self._apply_product_mapping(df, product_mapping_path)
                report['steps'].append("商品映射完成")
                if unmatched_skus:
                    report['unmatched']['product_skus'] = unmatched_skus
                    sku_list = unmatched_skus[:10]  # 最多显示10个
                    report['warnings'].append(f"⚠️ 未匹配的商品SKU ({len(unmatched_skus)}个): {', '.join(sku_list)}")
            
            # Step 7.5: 计算采购成本（销量 × 最新采购价）
            logger.info("Step 7.5: 计算采购成本")
            if '销量' in df.columns and '最新采购价' in df.columns:
                # 将销量和采购价转为数值类型
                df['销量'] = pd.to_numeric(df['销量'], errors='coerce').fillna(0)
                df['最新采购价'] = pd.to_numeric(df['最新采购价'], errors='coerce').fillna(0)
                # 计算采购成本
                df['采购成本'] = df['销量'] * df['最新采购价']
                
                # 如果是退货，成本取负
                if '中文意思' in df.columns:
                    refund_mask = df['中文意思'].astype(str).str.contains('退货', na=False)
                    df.loc[refund_mask, '采购成本'] = df.loc[refund_mask, '采购成本'] * -1
                    refund_count = refund_mask.sum()
                    if refund_count > 0:
                        logger.info(f"退货记录 {refund_count} 条，采购成本已取负")
                
                # 四舍五入到2位小数
                df['采购成本'] = df['采购成本'].round(2)
                logger.info(f"采购成本计算完成，非零记录: {(df['采购成本'] != 0).sum()} 条")
                report['steps'].append("采购成本计算完成")
            else:
                df['采购成本'] = 0
                logger.warning("未找到销量或最新采购价列，跳过采购成本计算")
            
            # 保存多维版本（逆透视前的宽表）
            df_multi_dim = df.copy()
            logger.info(f"多维版本: {len(df_multi_dim)} 行, {len(df_multi_dim.columns)} 列")
            
            # Step 8: 逆透视（数值列转为二维）
            logger.info("Step 8: 逆透视")
            df = self.unpivot_amount_columns(df)
            report['steps'].append(f"逆透视完成: {len(df)} 行")
            
            # 保存二维版本（原币种金额）- 在Step10之后从美元版反推
            # 原币版=美元版去掉汇率和金额(USD)列，金额列保持原币
            
            # Step 9: 匹配汇率并计算美元金额
            logger.info("Step 9: 匹配汇率")
            df, unmatched_rate = self.apply_exchange_rate(df)
            report['steps'].append("汇率匹配完成")
            if unmatched_rate:
                report['unmatched']['exchange_rates'] = [unmatched_rate]
                report['warnings'].append(f"⚠️ 未匹配的汇率: {unmatched_rate}")
            
            # Step 10: 匹配绩效维度和序列码
            logger.info("Step 10: 匹配绩效维度")
            df, unmatched_perf = self.match_performance_dimension(df)
            report['steps'].append("绩效维度匹配完成")
            if unmatched_perf:
                report['unmatched']['performance_dimensions'] = unmatched_perf
                report['warnings'].append(f"⚠️ 未匹配的绩效维度: {unmatched_perf}")
            
            # 二维美元版本（最终版本）
            df_2d_usd = df
            
            # 调整列顺序：原始列在前，新增计算列在后
            calculated_cols = ['结算周期', '中文意思', '匹配辅助列', '金额类型', '金额', '币种', '汇率', '金额(USD)', 
                             '账单字段序列码', '维度类型', '绩效表对应维度', '采购成本']
            original_cols = [col for col in df_2d_usd.columns if col not in calculated_cols]
            df_2d_usd = df_2d_usd[original_cols + [col for col in calculated_cols if col in df_2d_usd.columns]]
            
            # 二维原币版本：从美元版去掉汇率和金额(USD)，保留原币金额和序列码
            df_2d_local = df_2d_usd.copy()
            if '汇率' in df_2d_local.columns:
                df_2d_local = df_2d_local.drop(columns=['汇率'])
            if '金额(USD)' in df_2d_local.columns:
                df_2d_local = df_2d_local.drop(columns=['金额(USD)'])
            
            report['success'] = True
            report['total_rows_2d'] = len(df_2d_usd)
            report['total_rows_multi'] = len(df_multi_dim)
            
            logger.info(f"清洗完成: 二维版本 {len(df_2d_usd)} 行, 多维版本 {len(df_multi_dim)} 行")
            
        except Exception as e:
            logger.error(f"清洗失败: {e}")
            report['success'] = False
            report['errors'].append(str(e))
            raise
        
        return df_2d_usd, df_multi_dim, df_2d_local, report
    
    def _apply_product_mapping(self, df: pd.DataFrame, mapping_path: str) -> tuple:
        """
        应用商品映射（仅对SKU不为空的行进行匹配）
        支持两种匹配方式：
        1. 直接匹配：账单SKU = SELLERSKU
        2. FNSKU匹配：账单SKU = FNSKU → 获取对应的SELLERSKU信息
        
        Args:
            df: DataFrame
            mapping_path: 商品映射表路径
            
        Returns:
            (添加了商品映射列的DataFrame, 未匹配的SKU列表)
        """
        unmatched_skus = []
        try:
            product_df = pd.read_csv(mapping_path, encoding='utf-8-sig')
            
            # 查找SKU列（多种可能的列名）
            sku_col = self._find_column(product_df, ['SELLERSKU', 'SKU', 'sku', 'SellerSku'])
            
            if not sku_col:
                logger.warning("商品映射表未找到SKU列")
                return df, unmatched_skus
            
            # 构建映射字典 - 以SELLERSKU为key
            product_id_map = dict(zip(product_df[sku_col], product_df['产品ID']))
            asin_map = dict(zip(product_df[sku_col], product_df['ASIN']))
            category1_map = dict(zip(product_df[sku_col], product_df['一级大类']))
            category2_map = dict(zip(product_df[sku_col], product_df['二级类目']))
            category3_map = dict(zip(product_df[sku_col], product_df['三级类目']))
            price_map = dict(zip(product_df[sku_col], product_df['最新采购价']))
            
            # 构建FNSKU到SELLERSKU的映射（用于FNSKU匹配）- 向量化构建
            fnsku_to_sku_map = {}
            if 'FNSKU' in product_df.columns:
                fnsku_col = product_df['FNSKU'].fillna('').astype(str).str.strip()
                valid_fnsku_mask = fnsku_col != ''
                fnsku_to_sku_map = dict(zip(fnsku_col[valid_fnsku_mask], product_df.loc[valid_fnsku_mask, sku_col].astype(str)))
                logger.info(f"FNSKU映射表: {len(fnsku_to_sku_map)} 条")
            
            # 初始化新列
            df['产品ID'] = ''
            df['ASIN_映射'] = ''
            df['一级大类'] = ''
            df['二级类目'] = ''
            df['三级类目'] = ''
            df['最新采购价'] = None
            
            # 只对SKU不为空的行进行匹配
            sku_not_empty = df['SKU'].notna() & (df['SKU'] != '')
            
            if sku_not_empty.any():
                # 第一步：直接匹配SELLERSKU
                df.loc[sku_not_empty, '产品ID'] = df.loc[sku_not_empty, 'SKU'].map(product_id_map).fillna('')
                df.loc[sku_not_empty, 'ASIN_映射'] = df.loc[sku_not_empty, 'SKU'].map(asin_map).fillna('')
                df.loc[sku_not_empty, '一级大类'] = df.loc[sku_not_empty, 'SKU'].map(category1_map).fillna('')
                df.loc[sku_not_empty, '二级类目'] = df.loc[sku_not_empty, 'SKU'].map(category2_map).fillna('')
                df.loc[sku_not_empty, '三级类目'] = df.loc[sku_not_empty, 'SKU'].map(category3_map).fillna('')
                df.loc[sku_not_empty, '最新采购价'] = df.loc[sku_not_empty, 'SKU'].map(price_map)
                
                # 第二步：对未匹配的行，尝试FNSKU匹配 - 向量化版本
                if fnsku_to_sku_map:
                    unmatched_mask = sku_not_empty & (df['产品ID'] == '')
                    if unmatched_mask.any():
                        # 通过FNSKU找到对应的SELLERSKU
                        matched_skus = df.loc[unmatched_mask, 'SKU'].map(fnsku_to_sku_map)
                        fnsku_matched_mask = matched_skus.notna()
                        
                        if fnsku_matched_mask.any():
                            # 向量化：获取匹配到的seller_sku
                            matched_seller_skus = matched_skus[fnsku_matched_mask]
                            
                            # 通过map批量映射商品信息
                            df.loc[fnsku_matched_mask[fnsku_matched_mask].index, '产品ID'] = matched_seller_skus.map(product_id_map).fillna('').values
                            df.loc[fnsku_matched_mask[fnsku_matched_mask].index, 'ASIN_映射'] = matched_seller_skus.map(asin_map).fillna('').values
                            df.loc[fnsku_matched_mask[fnsku_matched_mask].index, '一级大类'] = matched_seller_skus.map(category1_map).fillna('').values
                            df.loc[fnsku_matched_mask[fnsku_matched_mask].index, '二级类目'] = matched_seller_skus.map(category2_map).fillna('').values
                            df.loc[fnsku_matched_mask[fnsku_matched_mask].index, '三级类目'] = matched_seller_skus.map(category3_map).fillna('').values
                            df.loc[fnsku_matched_mask[fnsku_matched_mask].index, '最新采购价'] = matched_seller_skus.map(price_map).values
                            
                            logger.info(f"FNSKU匹配: {fnsku_matched_mask.sum()} 条")
                
                # 统计匹配率（只统计SKU不为空的行）
                matched = len(df[sku_not_empty & (df['产品ID'] != '')])
                total = sku_not_empty.sum()
                unmatched_count = total - matched
                logger.info(f"商品映射: {matched}/{total} 条匹配成功 ({matched/total*100:.1f}%), {unmatched_count} 条未匹配")
                
                # 收集未匹配的SKU
                unmatched_skus = df[sku_not_empty & (df['产品ID'] == '')]['SKU'].unique().tolist()[:20]
            else:
                logger.info("无SKU数据，跳过商品映射")
                
        except Exception as e:
            logger.warning(f"商品映射失败: {e}")
        
        return df, unmatched_skus

    def unpivot_amount_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        逆透视：将多个数值列转换为"金额类型"+"金额"两列
        
        Args:
            df: 宽表DataFrame
            
        Returns:
            长表DataFrame
        """
        df = df.copy()
        
        # 数值列（金额列）- 需要逆透视的列
        amount_columns = [
            '商品销售收入', '商品销售税', '运费销售收入', '运费税', 
            '包装收入', '包装税', '折扣金额', '折扣税',
            '平台代扣代缴税额', '佣金', '运费', '其他交易费用', '其他'
        ]
        
        # 找出存在的数值列
        existing_amount_cols = [col for col in amount_columns if col in df.columns]
        
        if not existing_amount_cols:
            logger.warning("未找到数值列，跳过逆透视")
            return df
        
        logger.info(f"逆透视数值列: {existing_amount_cols}")
        
        # 标识列（不变的列）- 排除数值列和结算金额
        id_columns = [col for col in df.columns if col not in existing_amount_cols and col != '结算金额']
        
        logger.info(f"逆透视标识列: {id_columns[:10]}...")
        
        # 保存attrs（pd.melt会丢失attrs）
        saved_attrs = dict(df.attrs)
        # 执行逆透视（melt）
        df_long = pd.melt(
            df,
            id_vars=id_columns,
            value_vars=existing_amount_cols,
            var_name='金额类型',
            value_name='金额'
        )
        # 恢复attrs
        df_long.attrs.update(saved_attrs)
        
        # 过滤金额为0或空的行（使用绝对值<0.01过滤接近0的值）
        before_count = len(df_long)
        df_long['金额'] = pd.to_numeric(df_long['金额'], errors='coerce')
        df_long = df_long[(df_long['金额'].abs() > 0.001) & (df_long['金额'].notna())]
        after_count = len(df_long)
        
        logger.info(f"逆透视: {len(df)}行 × {len(existing_amount_cols)}列 → {after_count}行 (过滤{before_count - after_count}行零值/空值)")
        
        # 重置索引
        df_long = df_long.reset_index(drop=True)
        
        return df_long

    def apply_exchange_rate(self, df: pd.DataFrame) -> tuple:
        """
        匹配汇率并计算美元金额
        
        Args:
            df: DataFrame
            
        Returns:
            (添加了币种、汇率、金额(USD)列的DataFrame, 未匹配的汇率信息)
        """
        df = df.copy()
        unmatched_rate = None
        
        # 优先从文件属性中获取币种（从CSV头部提取）
        currency = df.attrs.get('currency', '')
        
        # 如果没有从文件提取到币种，则根据站点推断
        if not currency and '站点' in df.columns:
            site_to_currency = {
                'amazon.de': 'EUR', 'amazon.fr': 'EUR', 'amazon.it': 'EUR',
                'amazon.es': 'EUR', 'amazon.nl': 'EUR', 'amazon.ie': 'EUR', 'amazon.co.uk': 'GBP',
                'amazon.com': 'USD', 'amazon.ca': 'CAD', 'amazon.co.jp': 'JPY',
                'amazon.pl': 'PLN', 'amazon.se': 'SEK',
            }
            site = df['站点'].iloc[0] if len(df) > 0 else ''
            if pd.notna(site):
                site_str = str(site).lower().strip()
                for key, cur in site_to_currency.items():
                    if key in site_str:
                        currency = cur
                        break
        
        # 设置币种列
        df['币种'] = currency
        
        # 获取结算周期
        period = df['结算周期'].iloc[0] if '结算周期' in df.columns and len(df) > 0 else ''
        
        # 匹配汇率
        rate = None
        if currency and period:
            if currency == 'USD':
                rate = 1.0
            else:
                key = f"{currency}_{period}"
                rate = self.exchange_rates.get(key)
        
        df['汇率'] = rate
        
        # 确保金额列是数值类型
        if '金额' in df.columns:
            df['金额'] = pd.to_numeric(df['金额'], errors='coerce').fillna(0)
        
        # 计算美元金额
        if rate:
            # 向量化计算，避免apply(lambda)
            df['金额(USD)'] = np.round(df['金额'] * rate, 2)
            logger.info(f"汇率匹配: {currency} @ {rate}, 已计算金额(USD)")
        else:
            df['金额(USD)'] = None
            unmatched_rate = f"{currency}_{period}"
            logger.warning(f"未找到汇率: {unmatched_rate}")
        
        return df, unmatched_rate
    
    def match_performance_dimension(self, df: pd.DataFrame) -> tuple:
        """
        匹配绩效维度和序列码 - 向量化版本
        
        根据站点+中文意思+金额类型匹配账单字段序列码和绩效表对应维度
        
        Args:
            df: 包含站点、中文意思、金额类型列的DataFrame
            
        Returns:
            (添加了账单字段序列码、维度类型、绩效表对应维度列的DataFrame, 未匹配的key列表)
        """
        import time
        start_time = time.time()
        df = df.copy()
        
        logger.info(f"match_performance_dimension 向量化优化开始, 行数: {len(df)}")
        
        # 站点映射：amazon.de -> DE
        site_mapping = {
            'amazon.de': 'DE', 'amazon.fr': 'FR', 'amazon.it': 'IT',
            'amazon.es': 'ES', 'amazon.nl': 'NL', 'amazon.co.uk': 'UK',
            'amazon.com': 'US', 'amazon.ca': 'CA', 'amazon.co.jp': 'JP',
            'amazon.pl': 'PL', 'amazon.se': 'SE', 'amazon.be': 'BE',
            'amazon.ie': 'IE', 'amazon.com.mx': 'MX', 'amazon.com.br': 'BR',
            'amazon.au': 'AU', 'amazon.in': 'IN',
        }
        
        # 确定需要展示的关键列
        perf_detail_cols = ['站点', '中文意思', '金额类型', '匹配辅助列', '结算金额', 'SKU', '结算周期']
        perf_available_cols = [c for c in perf_detail_cols if c in df.columns]
        
        # ========== 第一步：向量化构建站点代码列 ==========
        site_series = df['站点'].astype(str).str.lower().str.strip() if '站点' in df.columns else pd.Series([''] * len(df), index=df.index)
        
        # 构建每个站点的匹配mask
        site_codes = []
        for domain, code in site_mapping.items():
            mask = site_series.str.contains(domain, regex=False, na=False)
            site_codes.extend([(mask, code)] * 1)
        
        # 第一步：先尝试匹配所有站点
        df['站点代码_temp'] = ''  # 初始为空
        for mask, code in site_codes:
            df.loc[mask, '站点代码_temp'] = code
        
        # 统计已匹配的站点分布，用多数决确定默认站点
        matched_site_counts = df.loc[df['站点代码_temp'] != '', '站点代码_temp'].value_counts()
        majority_site = matched_site_counts.index[0] if len(matched_site_counts) > 0 else 'DE'
        
        # 未匹配的行用多数决站点填充
        unmatched_site_mask = df['站点代码_temp'] == ''
        if unmatched_site_mask.any():
            df.loc[unmatched_site_mask, '站点代码_temp'] = majority_site
            unmatched_with_value = unmatched_site_mask & (site_series != '') & (site_series != 'nan')
            if unmatched_with_value.any():
                unrecognized_sites = df.loc[unmatched_with_value, '站点'].unique()[:5].tolist()
                logger.warning(f"无法识别的站点（已使用多数决{majority_site}映射）: {unrecognized_sites}")
        
        # 统计最终站点分布
        site_value_counts = df['站点代码_temp'].value_counts()
        logger.info(f"站点分布: {site_value_counts.to_dict()}")
        if len(site_value_counts) > 1:
            logger.info(f"站点多数决: {majority_site} ({site_value_counts.iloc[0]}条)")
        
        # ========== 第二步：向量化构建组合key并匹配 ==========
        chinese_series = df['中文意思'].astype(str).str.strip() if '中文意思' in df.columns else pd.Series([''] * len(df), index=df.index)
        amount_type_series = df['金额类型'].astype(str).str.strip() if '金额类型' in df.columns else pd.Series([''] * len(df), index=df.index)
        
        # 构建组合key
        df['perf_key'] = df['站点代码_temp'] + '_' + chinese_series + '_' + amount_type_series
        
        # 用map匹配
        perf_map = df['perf_key'].map(self.performance_mapping)
        
        # 拆分为3列
        df['账单字段序列码'] = perf_map.apply(lambda x: x['账单字段序列码'] if isinstance(x, dict) else '')
        df['维度类型'] = perf_map.apply(lambda x: x['维度类型'] if isinstance(x, dict) else '')
        df['绩效表对应维度'] = perf_map.apply(lambda x: x['绩效表对应维度'] if isinstance(x, dict) else '')
        
        # 统计匹配情况
        matched_mask = df['账单字段序列码'] != ''
        matched_count = matched_mask.sum()
        total = len(df)
        logger.info(f"绩效维度匹配: {matched_count}/{total} 条 ({matched_count/total*100:.1f}%)")
        
        # ========== 第三步：收集未匹配的样本（包含出现次数）============
        unmatched_mask = ~matched_mask
        unmatched_samples = []
        
        if unmatched_mask.any():
            # 获取未匹配的唯一key及其出现次数（按次数降序）
            unmatched_counts = df.loc[unmatched_mask, 'perf_key'].value_counts()
            
            logger.warning(f"未匹配样本（按出现次数降序）: {unmatched_counts.head(5).to_dict()}")
            
            # 按出现次数降序遍历前20个
            for key, count in unmatched_counts.head(20).items():
                sample_idx = df[df['perf_key'] == key].index[0]
                sample_row = df.loc[sample_idx]
                # 获取匹配辅助列原始值，便于排查哪个匹配列没匹配上中文意思
                helper_val = sample_row.get('匹配辅助列', '')
                helper_display = str(helper_val) if pd.notna(helper_val) else ''
                detail = {
                    '匹配key': key,
                    '出现次数': int(count),
                    '站点': df.loc[sample_idx, '站点代码_temp'],
                    '中文意思': chinese_series.loc[sample_idx],
                    '金额类型': amount_type_series.loc[sample_idx],
                    '匹配辅助列': helper_display
                }
                for col in perf_available_cols:
                    if col in ['站点', '中文意思', '金额类型', '匹配辅助列']:
                        continue
                    val = sample_row.get(col, '')
                    if pd.notna(val) and str(val).strip():
                        detail[col] = str(val).strip()
                unmatched_samples.append(detail)
        
        # 清理临时列
        df.drop(columns=['站点代码_temp', 'perf_key'], inplace=True)
        
        elapsed = time.time() - start_time
        logger.info(f"match_performance_dimension 完成, 耗时: {elapsed:.2f}秒")
        
        return df, unmatched_samples
    
    def _extract_currency_from_file(self, file_path: str) -> Optional[str]:
        """
        从CSV文件头部提取币种信息
        
        Args:
            file_path: CSV文件路径
            
        Returns:
            币种代码（如 'EUR', 'USD', 'GBP'），未找到返回 None
        """
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                lines = [f.readline() for _ in range(5)]  # 读取前5行
            
            # 货币关键词映射
            currency_map = {
                'EUR': ['EUR', 'EURO', '欧元'],
                'USD': ['USD', 'DOLLAR', '美元'],
                'GBP': ['GBP', 'POUND', '英镑'],
                'JPY': ['JPY', 'YEN', '日元', '円'],
                'CAD': ['CAD', 'CANADIAN', '加元'],
                'CNY': ['CNY', 'RMB', '人民币'],
                'PLN': ['PLN', 'ZLOTY', '兹罗提'],
                'SEK': ['SEK', 'KRONA', '克朗', 'i kr'],
            }
            
            # 检查前5行
            for line in lines:
                line_upper = line.upper()
                for currency, keywords in currency_map.items():
                    if any(kw in line_upper for kw in keywords):
                        logger.info(f"从文件检测到币种: {currency}")
                        return currency
            
            return None
            
        except Exception as e:
            logger.warning(f"提取币种信息失败: {e}")
            return None
