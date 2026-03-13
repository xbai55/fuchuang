## 项目概述
- **名称**: 反诈预警专家工作流
- **功能**: 通过整合文本、语音、图像信息，结合知识库与用户画像，为用户提供实时风险监测、个性化预警及监护人联动服务

### 节点清单
| 节点名 | 文件位置 | 类型 | 功能描述 | 分支逻辑 | 配置文件 |
|-------|---------|------|---------|---------|---------|
| multimodal_input | `nodes/multimodal_input_node.py` | task | 多模态输入处理（文本/语音/图片解析） | - | - |
| knowledge_search | `nodes/knowledge_search_node.py` | task | 知识库检索（RAG检索相似案例和法律依据） | - | - |
| risk_assessment | `nodes/risk_assessment_node.py` | agent | 风险评估（LLM分析风险评分） | →risk_decision | `config/risk_assessment_cfg.json` |
| risk_decision | `nodes/risk_decision_node.py` | condition | 风险分级决策 | "低风险处理"→intervention, "中风险处理"→intervention, "高风险处理"→intervention | - |
| intervention | `nodes/intervention_node.py` | agent | 干预措施生成（个性化预警文案） | →report_generation | `config/intervention_cfg.json` |
| report_generation | `nodes/report_generation_node.py` | agent | 报告生成（生成安全监测报告） | →END | `config/report_generation_cfg.json` |

**类型说明**: task(task节点) / agent(大模型) / condition(条件分支) / looparray(列表循环) / loopcond(条件循环)

## 子图清单
无子图

## 技能使用
- 节点`multimodal_input`使用技能：音频识别（ASR）、大语言模型（多模态理解）
- 节点`knowledge_search`使用技能：知识库（RAG检索）
- 节点`risk_assessment`、`intervention`、`report_generation`使用技能：大语言模型

## 工作流流程
1. **多模态输入处理** (multimodal_input): 接收文本、语音、图片输入，将语音转文字，使用多模态模型分析图片
2. **知识库检索** (knowledge_search): 基于处理后的文本内容，在知识库中检索相似案例和法律依据
3. **风险评估** (risk_assessment): 结合文本内容、相似案例、法律依据和用户角色，进行多维风险分析，给出评分（0-100）、等级和诈骗类型
4. **分级决策** (risk_decision): 根据风险评分决定处理流程（<40低风险，40-75中风险，>75高风险）
5. **干预措施** (intervention): 根据风险等级和用户角色生成个性化警告文案，判断是否通知监护人
6. **报告生成** (report_generation): 汇总所有分析结果，生成完整的Markdown格式安全监测报告

## 风险等级说明
- **低风险 (<40)**: 正常社交，无明显诈骗迹象，生成简要安全提示
- **中风险 (40-75)**: 疑似诈骗，触发弹窗警告，列举相似案例，建议复核身份
- **高风险 (>75)**: 高度可疑，立即触发干预，生成强硬警告文案，自动通知监护人

## 用户角色针对性
- **老人 (elderly)**: 语气温和、通俗易懂，强调与子女沟通
- **学生 (student)**: 语气友好、直接，警惕诱导消费与虚假兼职
- **财会人员 (finance)**: 语气专业、严肃，强调专业流程、法律责任与公章制度
- **通用用户 (general)**: 语气中性、客观，提供明确的安全建议
