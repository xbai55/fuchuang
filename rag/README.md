# 诈骗识别 RAG 知识库

这个项目提供一条可直接落地的链路：

`官方源爬取 -> 文档清洗分块 -> 向量化索引 -> 相似检索 -> 风险预警`

目标是围绕诈骗识别构建一个可追溯、可扩展的本地知识库，默认覆盖三类知识：

- 法律条文与司法解释
- 诈骗案例与典型判例
- 与诈骗识别相关的图片说明、照片类型和图文宣传素材

默认数据源优先使用公开官方站点：

- 中国人大网 `npc.gov.cn`
- 最高人民法院 `court.gov.cn`
- 中国政府网 `gov.cn`

## 设计原则

- 默认可跑通：开箱即用使用 TF-IDF 字符 n-gram 向量化，不依赖大模型。
- 可升级：如安装 `sentence-transformers`，可切换为语义嵌入。
- 可追溯：每条知识都保存来源 URL、发布时间、站点、标签。
- 可扩展：新增站点时补一个搜索或页面解析适配器即可。

## 知识类型

- `law`：法律条文、司法解释、规范性意见。
- `case`：典型案例、入库参考案例、诈骗案解析。
- `photo_type`：诈骗相关图片说明、照片类型、人工整理的图像风险模式。
- `image_article`：图文宣传稿、反诈图解等整页图文资料。

## 快速开始

推荐使用 `uv` 创建 Python 3.11 环境：

```bash
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -e .
```

构建知识库：

```bash
fraud-rag build --config configs/sources.example.yaml
```

相似检索：

```bash
fraud-rag query \
  --index-dir artifacts/index \
  --text "兼职刷单，先培训再返现，要求下载陌生APP"
```

诈骗预警：

```bash
fraud-rag warn \
  --index-dir artifacts/index \
  --text "对方自称客服，说包裹丢失，要求共享屏幕并转账验证" \
  --image-text "聊天截图中出现退款二维码和远程协助提示"
```

## 可选语义嵌入

如果需要更强的语义检索能力，可安装可选依赖并在配置中切换 `backend: sentence-transformer`：

```bash
uv pip install -e ".[semantic]"
```

默认示例模型字段是：

```yaml
index:
  backend: sentence-transformer
  dense_model: BAAI/bge-base-zh-v1.5
```

## 默认数据源策略

项目采用“种子 URL + 站内搜索”的混合方式：

- 法律重点文档用固定 URL 保证稳定。
- 案例和图文资料通过站内搜索扩展抓取。
- 图片知识既抓取官方图文稿件中的图片说明，也加载本地维护的照片类型种子。

## 输出物

构建后默认会生成这些文件：

- `data/raw/documents.jsonl`：原始文档
- `data/processed/documents.jsonl`：清洗后的文档
- `data/processed/chunks.jsonl`：分块后的知识片段
- `artifacts/index/manifest.json`：索引元信息
- `artifacts/index/chunks.jsonl`：索引对应的块元数据
- `artifacts/index/tfidf.joblib` 或 `artifacts/index/dense.joblib`

## 风险判定逻辑

预警不是简单关键词匹配，而是基于相似度命中结果进行聚合：

- 看 top-k 相似知识片段的分数
- 看命中的知识类别是否同时覆盖案例、法律、图片说明
- 汇总命中的诈骗子类型和标签
- 输出 `low / medium / high` 风险等级与处置建议

## 注意事项

- `gov.cn` 图片搜索接口当前已按 2026-03-27 验证可用。如果后续官方搜索页变更，更新 `fraud_rag.crawler.GOV_ATHENA_APP_KEY` 或直接改为固定种子 URL 即可。
- 本项目默认处理的是“文字输入、OCR 文本、图片描述、聊天记录、截图文案”等线索。若要直接对原始图片做视觉向量检索，可在此基础上接入 CLIP 或多模态模型。
- 预警结果适合做风控辅助，不应替代人工审核和执法判断。
