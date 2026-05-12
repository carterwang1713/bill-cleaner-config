"""
数据逆透视模块
将一维宽表转换为二维长表
"""
import pandas as pd
from typing import List, Optional, Tuple
from pathlib import Path
from loguru import logger

import sys
sys.path.append(str(Path(__file__).parent.parent))


class DataUnpivot:
    """
    数据逆透视处理器
    
    功能：
    1. 将宽表（多个金额列）转换为长表（金额类型+金额值）
    2. 支持自定义数值列和标识列
    3. 自动过滤零值和空值行
    
    使用示例：
        unpivot = DataUnpivot()
        df_long = unpivot.transform(df_wide)
    """
    
    def __init__(self):
        """初始化逆透视处理器"""
        # 默认数值列（金额列）- 不包含"结算金额"
        self._default_amount_columns = [
            '商品销售收入', '运费销售收入', '包装收入', '折扣金额',
            '已收取的销售税', '平台代扣代缴税额', '佣金', '运费',
            '其他交易费用', '其他'
        ]
        
        # 默认标识列（不变列）
        self._default_id_columns = [
            '结算日期', '结算单号', '结算类型', '订单号', 'SKU', '订单描述',
            '销量', '站点', '配送方式', '下单城市', '订单状态', '邮编',
            '匹配辅助列', '中文意思', '账单字段序列码', '绩效表对应维度',
            '站点代码', '币种', '结算时间', '结算周期'
        ]
        
        logger.info("逆透视处理器初始化完成")
    
    def transform(
        self,
        df: pd.DataFrame,
        amount_columns: Optional[List[str]] = None,
        id_columns: Optional[List[str]] = None,
        value_col_name: str = '金额',
        type_col_name: str = '金额类型',
        filter_zero: bool = True,
        filter_na: bool = True
    ) -> pd.DataFrame:
        """
        执行逆透视转换
        
        Args:
            df: 原始宽表DataFrame
            amount_columns: 数值列列表（默认使用内置金额列）
            id_columns: 标识列列表（默认自动检测非数值列）
            value_col_name: 金额值列名
            type_col_name: 金额类型列名
            filter_zero: 是否过滤金额为0的行
            filter_na: 是否过滤金额为空的行
            
        Returns:
            逆透视后的长表DataFrame
        """
        df = df.copy()
        
        # 确定数值列
        if amount_columns is None:
            amount_columns = [col for col in self._default_amount_columns if col in df.columns]
        
        if not amount_columns:
            logger.error("未找到数值列")
            return df
        
        logger.info(f"数值列: {amount_columns}")
        
        # 确定标识列
        if id_columns is None:
            # 自动检测：排除数值列，保留其他列
            id_columns = [col for col in df.columns if col not in amount_columns]
        
        logger.info(f"标识列: {id_columns}")
        
        # 执行逆透视（melt）
        try:
            df_long = pd.melt(
                df,
                id_vars=id_columns,
                value_vars=amount_columns,
                var_name=type_col_name,
                value_name=value_col_name
            )
            
            logger.info(f"逆透视完成: {len(df)}行 × {len(amount_columns)}列 → {len(df_long)}行")
            
            # 过滤零值
            if filter_zero:
                before_count = len(df_long)
                df_long = df_long[df_long[value_col_name] != 0]
                filtered_count = before_count - len(df_long)
                logger.info(f"过滤零值: 移除 {filtered_count} 行")
            
            # 过滤空值
            if filter_na:
                before_count = len(df_long)
                df_long = df_long[df_long[value_col_name].notna()]
                filtered_count = before_count - len(df_long)
                logger.info(f"过滤空值: 移除 {filtered_count} 行")
            
            # 重置索引
            df_long = df_long.reset_index(drop=True)
            
            # 统计
            logger.info(f"最终结果: {len(df_long)} 行")
            
            return df_long
            
        except Exception as e:
            logger.error(f"逆透视失败: {e}")
            return df
    
    def transform_file(
        self,
        input_file: str,
        output_file: str,
        **kwargs
    ) -> bool:
        """
        从文件读取并执行逆透视
        
        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径
            **kwargs: 传递给transform的其他参数
            
        Returns:
            是否成功
        """
        try:
            # 读取文件
            input_path = Path(input_file)
            if input_path.suffix.lower() == '.csv':
                df = pd.read_csv(input_file, encoding='utf-8-sig')
            else:
                df = pd.read_excel(input_file, engine='openpyxl')
            
            logger.info(f"读取文件: {input_file}, {len(df)} 行")
            
            # 执行逆透视
            df_long = self.transform(df, **kwargs)
            
            # 保存文件
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if output_path.suffix.lower() == '.csv':
                df_long.to_csv(output_file, index=False, encoding='utf-8-sig')
            else:
                df_long.to_excel(output_file, index=False, engine='openpyxl')
            
            logger.info(f"保存文件: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"文件处理失败: {e}")
            return False
    
    def get_column_stats(self, df: pd.DataFrame) -> dict:
        """
        获取列统计信息
        
        Args:
            df: DataFrame
            
        Returns:
            统计信息字典
        """
        amount_cols = [col for col in self._default_amount_columns if col in df.columns]
        other_cols = [col for col in df.columns if col not in amount_cols]
        
        stats = {
            '总行数': len(df),
            '总列数': len(df.columns),
            '数值列': amount_cols,
            '数值列数量': len(amount_cols),
            '标识列': other_cols,
            '标识列数量': len(other_cols),
            '预估逆透视后行数': len(df) * len(amount_cols)
        }
        
        # 统计各数值列的非零非空行数
        for col in amount_cols:
            if col in df.columns:
                non_zero = (df[col] != 0).sum()
                non_na = df[col].notna().sum()
                stats[f'{col}_非零行'] = non_zero
                stats[f'{col}_非空行'] = non_na
        
        return stats


# 导出类
__all__ = ['DataUnpivot']
