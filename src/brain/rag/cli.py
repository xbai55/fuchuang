"""
RAG 知识库 CLI 工具
提供命令行接口管理知识库
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import click

from src.brain.rag.pipeline import KnowledgePipeline
from src.brain.rag.indexer import SimilarityIndex
from src.brain.rag.detector import RiskDetector
from src.brain.rag.config import load_rag_config


@click.group()
@click.option("--config", default="config/rag.yaml", help="配置文件路径")
@click.pass_context
def rag(ctx: click.Context, config: str):
    """RAG 知识库管理工具"""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config


@rag.command()
@click.option("--backend", default=None, help="索引类型 (tfidf/sentence-transformer/hybrid)")
@click.pass_context
def build(ctx: click.Context, backend: Optional[str]):
    """构建知识库（爬取、分块、索引）"""
    config_path = ctx.obj["config_path"]

    if not Path(config_path).exists():
        click.echo(f"错误: 配置文件不存在: {config_path}")
        return

    config = load_rag_config(config_path)
    pipeline = KnowledgePipeline(config)

    click.echo("开始构建知识库...")
    click.echo(f"配置文件: {config_path}")
    click.echo(f"索引类型: {backend or config.index.backend}")

    try:
        stats = asyncio.run(pipeline.build_all(backend=backend))
        click.echo("\n构建完成!")
        click.echo(json.dumps(stats, ensure_ascii=False, indent=2))
    except Exception as e:
        click.echo(f"构建失败: {e}")
        raise click.ClickException(str(e))


@rag.command()
@click.option("--index-dir", default="artifacts/index", help="索引目录")
@click.option("--query", "-q", required=True, help="查询文本")
@click.option("--top-k", default=5, help="返回结果数量")
def query(index_dir: str, query: str, top_k: int):
    """执行相似检索"""
    index_path = Path(index_dir)

    if not index_path.exists():
        click.echo(f"错误: 索引目录不存在: {index_dir}")
        return

    try:
        index = SimilarityIndex.load(index_path)
        hits = index.search(query, top_k=top_k)

        click.echo(f"\n查询: {query}")
        click.echo(f"后端: {index.backend}")
        click.echo(f"结果数: {len(hits)}\n")

        for i, hit in enumerate(hits, 1):
            chunk = hit.chunk
            click.echo(f"{i}. [{hit.score:.4f}] {chunk.title}")
            click.echo(f"   类别: {chunk.category}")
            if chunk.subtype:
                click.echo(f"   子类型: {chunk.subtype}")
            click.echo(f"   来源: {chunk.source_site}")
            click.echo(f"   内容: {chunk.text[:100]}...\n")

    except Exception as e:
        click.echo(f"查询失败: {e}")
        raise click.ClickException(str(e))


@rag.command()
@click.option("--index-dir", default="artifacts/index", help="索引目录")
@click.option("--config", default="config/rag.yaml", help="配置文件路径")
@click.option("--text", "-t", default="", help="输入文本")
@click.option("--image-text", default="", help="图片OCR文本")
@click.option("--ocr-text", default="", help="OCR文本")
@click.option("--top-k", default=5, help="返回结果数量")
def warn(
    index_dir: str,
    config: str,
    text: str,
    image_text: str,
    ocr_text: str,
    top_k: int,
):
    """执行诈骗风险预警"""
    index_path = Path(index_dir)

    if not index_path.exists():
        click.echo(f"错误: 索引目录不存在: {index_dir}")
        return

    # 组合查询文本
    query_parts = [p for p in [text, image_text, ocr_text] if p.strip()]
    query_text = "\n".join(query_parts)

    if not query_text:
        click.echo("错误: 请提供至少一种输入 (--text, --image-text, --ocr-text)")
        return

    try:
        # 加载索引和配置
        index = SimilarityIndex.load(index_path)

        if Path(config).exists():
            rag_config = load_rag_config(config)
            detector = RiskDetector(
                high_threshold=rag_config.warning.high_threshold,
                medium_threshold=rag_config.warning.medium_threshold,
            )
        else:
            detector = RiskDetector()

        # 执行检索
        hits = index.search(query_text, top_k=top_k)

        # 执行风险评估
        result = detector.assess(query_text, hits)

        # 输出结果
        click.echo(f"\n{'='*50}")
        click.echo("诈骗风险预警报告")
        click.echo(f"{'='*50}\n")

        # 风险等级
        level_colors = {
            "high": ("red", "🔴 高风险"),
            "medium": ("yellow", "🟡 中风险"),
            "low": ("green", "🟢 低风险"),
        }
        level_color, level_text = level_colors.get(result.risk_level, ("white", result.risk_level))
        click.echo(click.style(f"风险等级: {level_text}", fg=level_color, bold=True))
        click.echo(f"置信度: {result.confidence:.2%}")

        # 识别的类型
        if result.matched_subtypes:
            click.echo(f"\n识别诈骗类型:")
            for subtype in result.matched_subtypes:
                click.echo(f"  - {subtype}")

        # 标签
        if result.matched_tags:
            click.echo(f"\n风险标签: {', '.join(result.matched_tags)}")

        # 建议
        click.echo(f"\n处置建议:")
        for i, rec in enumerate(result.recommendations, 1):
            click.echo(f"  {i}. {rec}")

        # 参考知识
        click.echo(f"\n参考知识 ({len(result.hits)}条):")
        for hit in result.hits[:3]:
            click.echo(f"  - [{hit['score']:.4f}] {hit['title']} ({hit['category']})")

        click.echo(f"\n{'='*50}")

        # 输出 JSON
        if click.confirm("\n是否输出 JSON 格式?"):
            click.echo(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    except Exception as e:
        click.echo(f"预警失败: {e}")
        raise click.ClickException(str(e))


@rag.command()
@click.option("--index-dir", default="artifacts/index", help="索引目录")
def stats(index_dir: str):
    """查看索引统计信息"""
    index_path = Path(index_dir)

    if not index_path.exists():
        click.echo(f"错误: 索引目录不存在: {index_dir}")
        return

    try:
        index = SimilarityIndex.load(index_path)
        stats_info = index.get_stats()

        click.echo(f"\n索引统计信息:")
        click.echo(f"{'='*40}")
        click.echo(f"后端类型: {stats_info['backend']}")
        click.echo(f"模型名称: {stats_info.get('model_name', 'N/A')}")
        click.echo(f"知识片段数: {stats_info['chunk_count']}")
        click.echo(f"索引路径: {index_dir}")

    except Exception as e:
        click.echo(f"加载失败: {e}")
        raise click.ClickException(str(e))


@rag.command()
@click.pass_context
def config_info(ctx: click.Context):
    """查看当前配置"""
    config_path = ctx.obj["config_path"]

    if not Path(config_path).exists():
        click.echo(f"配置文件不存在: {config_path}")
        return

    try:
        config = load_rag_config(config_path)

        click.echo(f"\n配置信息:")
        click.echo(f"{'='*40}")
        click.echo(f"配置文件: {config_path}")
        click.echo(f"\n索引配置:")
        click.echo(f"  后端: {config.index.backend}")
        click.echo(f"  密集模型: {config.index.dense_model}")
        click.echo(f"  分块大小: {config.index.chunk_size}")
        click.echo(f"  分块重叠: {config.index.chunk_overlap}")
        click.echo(f"  Top-K: {config.index.top_k}")

        click.echo(f"\n风险阈值:")
        click.echo(f"  高风险: {config.warning.high_threshold}")
        click.echo(f"  中风险: {config.warning.medium_threshold}")

        click.echo(f"\n数据源:")
        click.echo(f"  种子URL: {len(config.sources.seed_urls)}个")
        click.echo(f"  人大网搜索: {'启用' if config.sources.npc.enabled else '禁用'}")
        click.echo(f"  法院网搜索: {'启用' if config.sources.court.enabled else '禁用'}")
        click.echo(f"  政府图片: {'启用' if config.sources.gov_images.enabled else '禁用'}")

        click.echo(f"\n路径:")
        click.echo(f"  原始文档: {config.paths.raw_documents}")
        click.echo(f"  分块数据: {config.paths.chunks}")
        click.echo(f"  索引目录: {config.paths.index_dir}")

    except Exception as e:
        click.echo(f"加载配置失败: {e}")
        raise click.ClickException(str(e))


def main():
    """CLI 入口点"""
    rag()


if __name__ == "__main__":
    main()
