"""
报表生成模块 v3.0
严格按照固定格式生成报表
"""
import pandas as pd
from typing import Dict, Optional
from pathlib import Path
from loguru import logger

import sys
sys.path.append(str(Path(__file__).parent.parent))


class ReportGenerator:
    """
    报表生成器 v3.0
    
    功能：
    1. 按固定序列码格式生成报表
    2. 没有值的项目显示0
    3. 严格按照图片格式
    """
    
    def __init__(self):
        """初始化报表生成器"""
        # 固定的报表格式（序列码 -> 项目名称）
        self._report_format = {
            '收入': {
                1: 'FBM销售金额',
                2: 'FBM退款金额',
                3: 'FBA销售金额',
                4: 'FBA退款金额',
                5: 'FBA库存津贴',
                6: 'FBA清算收益',
                7: 'FBA清算收益调整',
                8: '运费收入',
                9: '运费收入调整',
                10: '仓储收入',
                11: '仓储收入调整',
                12: '折扣金额',
                13: '折扣金额退回',
                14: 'A-TO-Z担保索赔',
                15: '信用卡退款/银行拒付',
                16: '运费索赔',
                17: 'SAFE-T退款',
                44: '亚马逊积分费用',
                45: '亚马逊积分费用-退货'
            },
            '费用': {
                18: '提现金额',
                19: '补偿发放失败调整',
                20: '预提费用',
                21: '应付亚马逊其他款项',
                23: '销售佣金',
                24: '销售佣金-退货',
                25: 'FBA配送费',
                26: 'FBA配送费调整',
                27: '其他交易费用',
                28: '其他交易费用-退货',
                29: 'FBA仓储费',
                30: '卖家承担退回运费',
                32: '运费调整',
                33: '其他服务费',
                34: '其他服务费调整',
                35: '其他调整',
                36: '广告费',
                37: '广告费退款',
                38: '清仓-服务费',
                46: '客户货款追回'
            },
            '税费': {
                41: '商品销售税',
                42: '商品销售税-退货',
                43: '平台代扣代缴税额'
            }
        }
        
        # 金额类型到序列码的映射
        self._amount_to_sequence = {
            '商品销售收入': 3,
            '运费销售收入': 8,
            '包装收入': 10,
            '折扣金额': 12,
            '佣金': 23,
            '运费': 25,
            '其他交易费用': 27,
            '其他': 25,  # 其他归入FBA配送费
            '已收取的销售税': 41,
            '平台代扣代缴税额': 43
        }
        
        logger.info("报表生成器v3.0初始化完成")
    
    def generate(
        self,
        df: pd.DataFrame,
        site: str = None,
        period: str = None
    ) -> pd.DataFrame:
        """
        生成报表
        
        Args:
            df: 二维版数据
            site: 站点
            period: 结算周期
            
        Returns:
            报表DataFrame
        """
        df = df.copy()
        
        # 确定站点和周期
        if not site and '站点代码' in df.columns:
            site = str(df['站点代码'].mode().iloc[0]) if len(df) > 0 else ''
        if not period and '结算周期' in df.columns:
            period = str(df['结算周期'].mode().iloc[0]) if len(df) > 0 else ''
        
        # 按金额类型汇总
        if '金额类型' in df.columns and '金额' in df.columns:
            amount_summary = df.groupby('金额类型')['金额'].sum().to_dict()
        else:
            amount_summary = {}
        
        # 构建报表
        rows = []
        
        # 顶部汇总栏
        rows.append({'序列码': '', '项目': '查询站点', '借': '', '贷': site or ''})
        rows.append({'序列码': '', '项目': '结算周期', '借': '', '贷': period or ''})
        
        # 计算分类汇总
        income_total = self._calc_category_total(amount_summary, '收入')
        expense_total = self._calc_category_total(amount_summary, '费用')
        tax_total = self._calc_category_total(amount_summary, '税费')
        withdrawal_total = 0
        diff_total = income_total + expense_total + tax_total
        
        rows.append({'序列码': '', '项目': '收入合计', '借': '', '贷': round(income_total, 2) if income_total != 0 else 0})
        rows.append({'序列码': '', '项目': '费用合计', '借': round(abs(expense_total), 2) if expense_total != 0 else 0, '贷': ''})
        rows.append({'序列码': '', '项目': '税费合计', '借': '', '贷': round(tax_total, 2) if tax_total != 0 else 0})
        rows.append({'序列码': '', '项目': '提现合计', '借': withdrawal_total, '贷': ''})
        rows.append({'序列码': '', '项目': '差额合计', '借': '', '贷': round(diff_total, 2) if diff_total != 0 else 0})
        rows.append({'序列码': '', '项目': '', '借': '', '贷': ''})
        
        # 收入类明细
        rows.append({'序列码': '', '项目': '【收入类明细】', '借': '', '贷': ''})
        for seq, name in self._report_format['收入'].items():
            debit, credit = self._get_debit_credit(amount_summary, seq, name)
            rows.append({'序列码': seq, '项目': name, '借': debit, '贷': credit})
        rows.append({'序列码': '', '项目': '', '借': '', '贷': ''})
        
        # 费用类明细
        rows.append({'序列码': '', '项目': '【费用类明细】', '借': '', '贷': ''})
        for seq, name in self._report_format['费用'].items():
            debit, credit = self._get_debit_credit(amount_summary, seq, name)
            rows.append({'序列码': seq, '项目': name, '借': debit, '贷': credit})
        rows.append({'序列码': '', '项目': '', '借': '', '贷': ''})
        
        # 税费类明细
        rows.append({'序列码': '', '项目': '【税费类明细】', '借': '', '贷': ''})
        for seq, name in self._report_format['税费'].items():
            debit, credit = self._get_debit_credit(amount_summary, seq, name)
            rows.append({'序列码': seq, '项目': name, '借': debit, '贷': credit})
        
        return pd.DataFrame(rows)
    
    def _calc_category_total(self, amount_summary: dict, category: str) -> float:
        """计算分类汇总"""
        total = 0.0
        for seq, name in self._report_format.get(category, {}).items():
            # 查找对应的金额
            for amount_type, amount in amount_summary.items():
                mapped_seq = self._amount_to_sequence.get(amount_type)
                if mapped_seq == seq:
                    total += amount
        return total
    
    def _get_debit_credit(self, amount_summary: dict, seq: int, name: str) -> tuple:
        """获取借贷金额"""
        amount = 0.0
        found = False
        
        # 合并所有映射到该序列码的金额类型
        for amount_type, amt in amount_summary.items():
            mapped_seq = self._amount_to_sequence.get(amount_type)
            if mapped_seq == seq:
                amount += amt
                found = True
        
        if not found:
            return 0, 0
        
        # 正数在贷方，负数在借方
        if amount > 0:
            return 0, round(abs(amount), 2)
        else:
            return round(abs(amount), 2), 0
    
    def generate_excel(
        self,
        df: pd.DataFrame,
        output_file: str,
        site: str = None,
        period: str = None
    ) -> bool:
        """
        生成Excel报表
        
        Args:
            df: 二维版数据
            output_file: 输出文件路径
            site: 站点
            period: 结算周期
            
        Returns:
            是否成功
        """
        try:
            report_df = self.generate(df, site, period)
            
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            report_df.to_excel(output_file, index=False, engine='openpyxl')
            logger.info(f"报表已导出: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"导出报表失败: {e}")
            return False


# 导出类
__all__ = ['ReportGenerator']
