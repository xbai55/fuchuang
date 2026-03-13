from typing import Literal, Optional, List
from pydantic import BaseModel, Field
from utils.file.file import File

# ==================== 全局状态 ====================
class GlobalState(BaseModel):
    """工作流全局状态"""
    # 输入数据
    input_text: str = Field(default="", description="用户输入的文本内容")
    input_audio: Optional[File] = Field(default=None, description="用户上传的语音文件")
    input_image: Optional[File] = Field(default=None, description="用户上传的图片/截图")
    
    # 用户画像
    user_role: str = Field(default="general", description="用户角色：elderly(老人)/student(学生)/finance(财会人员)/general(通用)")
    guardian_name: str = Field(default="", description="监护人姓名")
    
    # 多模态处理结果
    processed_text: str = Field(default="", description="处理后的文本内容（包含语音转文字后的完整内容）")
    image_analysis: str = Field(default="", description="图片分析结果")
    
    # 知识库检索结果
    similar_cases: List[str] = Field(default=[], description="相似案例列表")
    legal_basis: str = Field(default="", description="法律依据")
    
    # 风险评估结果
    risk_score: int = Field(default=0, description="风险评分（0-100）")
    risk_level: str = Field(default="low", description="风险等级：low/medium/high")
    scam_type: str = Field(default="", description="诈骗类型")
    risk_clues: str = Field(default="", description="关键风险线索")
    
    # 干预措施
    warning_message: str = Field(default="", description="警告文案")
    guardian_alert: bool = Field(default=False, description="是否需要通知监护人")
    alert_reason: str = Field(default="", description="通知监护人的原因")
    
    # 最终报告
    final_report: str = Field(default="", description="最终的安全监测报告")

# ==================== 工作流输入输出 ====================
class GraphInput(BaseModel):
    """工作流输入"""
    input_text: str = Field(default="", description="用户输入的文本内容")
    input_audio: Optional[File] = Field(default=None, description="用户上传的语音文件")
    input_image: Optional[File] = Field(default=None, description="用户上传的图片/截图")
    user_role: str = Field(default="general", description="用户角色：elderly(老人)/student(学生)/finance(财会人员)/general(通用)")
    guardian_name: str = Field(default="", description="监护人姓名")

class GraphOutput(BaseModel):
    """工作流输出"""
    risk_score: int = Field(..., description="风险评分（0-100）")
    risk_level: str = Field(..., description="风险等级：low/medium/high")
    scam_type: str = Field(..., description="诈骗类型")
    warning_message: str = Field(..., description="警告文案")
    final_report: str = Field(..., description="最终的安全监测报告")
    guardian_alert: bool = Field(..., description="是否需要通知监护人")

# ==================== 多模态输入处理节点 ====================
class MultimodalInputNodeInput(BaseModel):
    """多模态输入处理节点的输入"""
    input_text: str = Field(..., description="用户输入的文本内容")
    input_audio: Optional[File] = Field(default=None, description="用户上传的语音文件")
    input_image: Optional[File] = Field(default=None, description="用户上传的图片/截图")

class MultimodalInputNodeOutput(BaseModel):
    """多模态输入处理节点的输出"""
    processed_text: str = Field(..., description="处理后的文本内容")
    image_analysis: str = Field(default="", description="图片分析结果")

# ==================== 知识库检索节点 ====================
class KnowledgeSearchNodeInput(BaseModel):
    """知识库检索节点的输入"""
    processed_text: str = Field(..., description="处理后的文本内容")

class KnowledgeSearchNodeOutput(BaseModel):
    """知识库检索节点的输出"""
    similar_cases: List[str] = Field(..., description="相似案例列表")
    legal_basis: str = Field(..., description="法律依据")

# ==================== 风险评估节点 ====================
class RiskAssessmentNodeInput(BaseModel):
    """风险评估节点的输入"""
    processed_text: str = Field(..., description="处理后的文本内容")
    similar_cases: List[str] = Field(default=[], description="相似案例列表")
    legal_basis: str = Field(default="", description="法律依据")
    user_role: str = Field(default="general", description="用户角色")
    image_analysis: str = Field(default="", description="图片分析结果")

class RiskAssessmentNodeOutput(BaseModel):
    """风险评估节点的输出"""
    risk_score: int = Field(..., description="风险评分（0-100）")
    risk_level: str = Field(..., description="风险等级：low/medium/high")
    scam_type: str = Field(..., description="诈骗类型")
    risk_clues: str = Field(..., description="关键风险线索")

# ==================== 分级决策节点 ====================
class RiskDecisionNodeInput(BaseModel):
    """分级决策节点的输入"""
    risk_score: int = Field(..., description="风险评分")
    risk_level: str = Field(..., description="风险等级")

class RiskDecisionNodeOutput(BaseModel):
    """分级决策节点的输出"""
    decision: str = Field(..., description="决策：low_risk/medium_risk/high_risk")

# ==================== 干预措施节点 ====================
class InterventionNodeInput(BaseModel):
    """干预措施节点的输入"""
    risk_score: int = Field(..., description="风险评分")
    risk_level: str = Field(..., description="风险等级")
    scam_type: str = Field(..., description="诈骗类型")
    risk_clues: str = Field(..., description="关键风险线索")
    similar_cases: List[str] = Field(default=[], description="相似案例列表")
    legal_basis: str = Field(default="", description="法律依据")
    user_role: str = Field(default="general", description="用户角色")
    guardian_name: str = Field(default="", description="监护人姓名")

class InterventionNodeOutput(BaseModel):
    """干预措施节点的输出"""
    warning_message: str = Field(..., description="警告文案")
    guardian_alert: bool = Field(..., description="是否需要通知监护人")
    alert_reason: str = Field(default="", description="通知监护人的原因")

# ==================== 报告生成节点 ====================
class ReportGenerationNodeInput(BaseModel):
    """报告生成节点的输入"""
    risk_score: int = Field(..., description="风险评分")
    risk_level: str = Field(..., description="风险等级")
    scam_type: str = Field(..., description="诈骗类型")
    risk_clues: str = Field(..., description="关键风险线索")
    similar_cases: List[str] = Field(default=[], description="相似案例列表")
    legal_basis: str = Field(default="", description="法律依据")
    warning_message: str = Field(..., description="警告文案")
    guardian_alert: bool = Field(..., description="是否需要通知监护人")
    alert_reason: str = Field(default="", description="通知监护人的原因")

class ReportGenerationNodeOutput(BaseModel):
    """报告生成节点的输出"""
    final_report: str = Field(..., description="最终的安全监测报告")
