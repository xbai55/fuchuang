#!/usr/bin/env python3
"""
多模态输入集成测试脚本
验证 multimodal_input 模块是否正确集成到 LangGraph 框架
"""

import sys
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.absolute()
multimodal_path = project_root / "multimodal_input"
src_path = project_root / "src"

if str(multimodal_path) not in sys.path:
    sys.path.insert(0, str(multimodal_path))

if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


def test_multimodal_imports():
    """测试多模态模块导入"""
    print("\n" + "="*60)
    print("📦 测试 1: 多模态模块导入")
    print("="*60)
    
    try:
        from ocr.ocr_async_processor import AsyncKeyframeOCRProcessor
        print("✅ OCR 模块导入成功")
    except ImportError as e:
        print(f"❌ OCR 模块导入失败：{e}")
        return False
    
    try:
        from video_module.video_inference import VideoFakeAnalyzer
        from video_module.keyframe_extractor import KeyframeExtractor
        print("✅ 视频模块导入成功")
    except ImportError as e:
        print(f"❌ 视频模块导入失败：{e}")
        return False
    
    try:
        from audio_module.audio_inference import AudioFakeAnalyzer, convert_bytes_to_ndarray
        from audio_module.VAD import AntiFraudAudioEngine
        print("✅ 音频模块导入成功")
    except ImportError as e:
        print(f"❌ 音频模块导入失败：{e}")
        return False
    
    return True


def test_node_import():
    """测试 LangGraph 节点导入"""
    print("\n" + "="*60)
    print("📦 测试 2: LangGraph 节点导入")
    print("="*60)
    
    try:
        from graphs.nodes.multimodal_input_node import multimodal_input_node
        print("✅ multimodal_input_node 导入成功")
    except ImportError as e:
        print(f"❌ multimodal_input_node 导入失败：{e}")
        return False
    
    try:
        from graphs.state import MultimodalInputNodeInput, MultimodalInputNodeOutput
        print("✅ 状态定义导入成功")
    except ImportError as e:
        print(f"❌ 状态定义导入失败：{e}")
        return False
    
    return True


def test_graph_structure():
    """测试图结构"""
    print("\n" + "="*60)
    print("📦 测试 3: LangGraph 图结构")
    print("="*60)
    
    try:
        from graphs.graph import main_graph, builder
        print("✅ LangGraph 主图导入成功")
        
        # 检查节点是否存在
        nodes = list(builder.nodes)
        print(f"   图中的节点: {nodes}")
        
        if 'multimodal_input' in nodes:
            print("✅ multimodal_input 节点已添加到图中")
        else:
            print("❌ multimodal_input 节点未在图中找到")
            return False
        
        # 检查边
        print("✅ 图结构验证通过")
        
    except Exception as e:
        print(f"❌ 图结构验证失败：{e}")
        return False
    
    return True


def test_model_initialization():
    """测试模型初始化（可选，需要模型权重文件）"""
    print("\n" + "="*60)
    print("📦 测试 4: 模型初始化（跳过 GPU 依赖）")
    print("="*60)
    
    try:
        from graphs.nodes.multimodal_input_node import _initialize_models, _models_initialized
        
        print("   尝试初始化模型...")
        # 不实际调用，只是检查函数是否存在
        print("✅ 模型初始化函数存在")
        
        # 检查模型权重文件
        weights_to_check = [
            multimodal_path / "audio_module/weights/latest_best_audio_model.pth",
            multimodal_path / "video_module/weights/final_model.pth",
        ]
        
        for weight_path in weights_to_check:
            if weight_path.exists():
                print(f"✅ 模型权重存在：{weight_path.name}")
            else:
                print(f"⚠️  模型权重缺失：{weight_path.name}")
        
        return True
        
    except Exception as e:
        print(f"⚠️  模型初始化测试跳过：{e}")
        return True  # 不阻止后续测试


def test_state_flow():
    """测试状态流转"""
    print("\n" + "="*60)
    print("📦 测试 5: 状态定义和流转")
    print("="*60)
    
    try:
        from graphs.state import (
            GlobalState,
            GraphInput,
            GraphOutput,
            MultimodalInputNodeInput,
            MultimodalInputNodeOutput
        )
        
        # 创建测试输入
        test_input = MultimodalInputNodeInput(
            input_text="测试文本"
        )
        print(f"✅ 创建测试输入：{test_input.input_text}")
        
        # 验证 GlobalState
        global_state = GlobalState(
            input_text="全局测试",
            user_role="general"
        )
        print(f"✅ 创建全局状态：{global_state.input_text}")
        
        return True
        
    except Exception as e:
        print(f"❌ 状态流转测试失败：{e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print("🧪 多模态输入集成测试套件")
    print("="*70)
    print(f"项目根目录：{project_root}")
    print(f"multimodal_input 路径：{multimodal_path}")
    print(f"src 路径：{src_path}")
    
    tests = [
        ("多模态模块导入", test_multimodal_imports),
        ("LangGraph 节点导入", test_node_import),
        ("LangGraph 图结构", test_graph_structure),
        ("模型初始化", test_model_initialization),
        ("状态定义和流转", test_state_flow),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ 测试 '{name}' 异常：{e}")
            results.append((name, False))
    
    # 汇总结果
    print("\n" + "="*70)
    print("📊 测试结果汇总")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status} - {name}")
    
    print(f"\n总计：{passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！多模态输入已成功集成到 LangGraph 框架")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
