#!/usr/bin/env python3
"""
反诈预警系统 - 统一启动脚本
集成 multimodal 多模态输入到 LangGraph 框架
"""

import os
import sys
import argparse
import subprocess
import time
from pathlib import Path


def get_project_root():
    """获取项目根目录"""
    return Path(__file__).parent.absolute()


def check_environment():
    """检查运行环境"""
    project_root = get_project_root()
    
    # 检查必要的目录
    required_dirs = [
        project_root / "src",
        project_root / "multimodal_input",
        project_root / "config",
    ]
    
    for dir_path in required_dirs:
        if not dir_path.exists():
            print(f"❌ 错误：必要目录不存在 - {dir_path}")
            return False
    
    # 检查模型权重文件
    print("\n📦 检查模型权重文件...")
    required_weights = [
        ("multimodal_input/audio_module/weights/latest_best_audio_model.pth", "音频深度伪造检测模型"),
        ("multimodal_input/video_module/weights/final_model.pth", "视频深度伪造检测模型"),
    ]
    
    missing_weights = []
    for weight_path, description in required_weights:
        full_path = project_root / weight_path
        if not full_path.exists():
            missing_weights.append((weight_path, description))
        else:
            print(f"✅ {description}: 已找到")
    
    if missing_weights:
        print("\n⚠️  警告：以下模型权重文件缺失：")
        for path, desc in missing_weights:
            print(f"   - {desc}: {path}")
        print("   服务仍会启动，但对应功能将不可用\n")
    else:
        print("\n✅ 所有模型权重文件均已找到\n")
    
    return True


def start_multimodal_service(port=8000):
    """启动多模态处理服务（独立 FastAPI 服务）"""
    project_root = get_project_root()
    multimodal_dir = project_root / "multimodal_input"
    
    print(f"\n🚀 启动多模态处理服务 (端口 {port})...")
    
    # 设置环境变量
    env = os.environ.copy()
    env['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
    
    # 添加 multimodal_input 到 Python 路径
    if str(multimodal_dir) not in sys.path:
        sys.path.insert(0, str(multimodal_dir))
    
    cmd = [sys.executable, str(multimodal_dir / "main.py"), "--port", str(port)]
    
    try:
        process = subprocess.Popen(
            cmd,
            env=env,
            cwd=str(multimodal_dir)
        )
        print(f"✅ 多模态处理服务已启动 -> http://localhost:{port}")
        return process
    except Exception as e:
        print(f"❌ 启动多模态服务失败：{e}")
        return None


def start_langgraph_server(port=5000):
    """启动 LangGraph 主服务器"""
    project_root = get_project_root()
    src_dir = project_root / "src"
    
    print(f"\n🤖 启动 LangGraph 主服务器 (端口 {port})...")
    
    # 设置环境变量
    env = os.environ.copy()
    
    # 添加项目根目录到 Python 路径，确保可以导入 multimodal_input 模块
    pythonpath = env.get('PYTHONPATH', '')
    if str(project_root) not in pythonpath:
        env['PYTHONPATH'] = str(project_root) + os.pathsep + pythonpath
    
    cmd = [
        sys.executable, "-m", "uvicorn", 
        "main:app",
        "--host", "0.0.0.0",
        "--port", str(port),
        "--reload"
    ]
    
    try:
        process = subprocess.Popen(
            cmd,
            env=env,
            cwd=str(src_dir)
        )
        print(f"✅ LangGraph 主服务器已启动 -> http://localhost:{port}")
        return process
    except Exception as e:
        print(f"❌ 启动 LangGraph 服务器失败：{e}")
        return None


def run_single_mode(mode: str, node_id: str = "", input_data: str = ""):
    """运行单点测试模式"""
    project_root = get_project_root()
    src_dir = project_root / "src"
    
    # 设置环境变量
    env = os.environ.copy()
    env['PYTHONPATH'] = str(project_root) + os.pathsep + env.get('PYTHONPATH', '')
    env['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
    
    cmd = [
        sys.executable,
        str(src_dir / "main.py"),
        "-m", mode,
        "-p", "5000"
    ]
    
    if node_id:
        cmd.extend(["-n", node_id])
    
    if input_data:
        cmd.extend(["-i", input_data])
    
    try:
        subprocess.run(cmd, env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ 运行失败：{e}")
        sys.exit(1)


def start_all_services(multimodal_port=8000, langgraph_port=5000):
    """启动所有服务"""
    print("\n" + "="*60)
    print("🎯 反诈预警专家工作流 - 启动中")
    print("="*60)
    
    # 检查环境
    if not check_environment():
        sys.exit(1)
    
    processes = []
    
    # 启动多模态服务
    multimodal_process = start_multimodal_service(port=multimodal_port)
    if multimodal_process:
        processes.append(("多模态处理服务", multimodal_process))
        time.sleep(2)  # 等待服务预热
    
    # 启动 LangGraph 主服务器
    langgraph_process = start_langgraph_server(port=langgraph_port)
    if langgraph_process:
        processes.append(("LangGraph 主服务器", langgraph_process))
    
    if not processes:
        print("\n❌ 没有服务成功启动")
        sys.exit(1)
    
    # 显示服务信息
    print("\n" + "="*60)
    print("✅ 所有服务已启动！")
    print("="*60)
    print("\n📋 服务列表:")
    for name, _ in processes:
        print(f"   • {name}")
    
    print(f"\n🔗 API 端点:")
    print(f"   • 多模态处理接口：http://localhost:{multimodal_port}/api/v1/analyze_multimodal")
    print(f"   • LangGraph 主接口：http://localhost:{langgraph_port}/run")
    print(f"   • 健康检查：http://localhost:{langgraph_port}/health")
    
    print("\n💡 使用示例:")
    print(f"   curl -X POST http://localhost:{langgraph_port}/run \\")
    print(f"     -H \"Content-Type: application/json\" \\")
    print(f"     -d '{{\"input_text\": \"你好，我收到了一个可疑链接\"}}'")
    
    print("\n按 Ctrl+C 停止所有服务\n")
    
    try:
        # 等待所有进程
        for name, process in processes:
            process.wait()
    except KeyboardInterrupt:
        print("\n\n🛑 正在停止服务...")
        for name, process in processes:
            try:
                process.terminate()
                process.wait(timeout=5)
                print(f"✅ {name} 已停止")
            except subprocess.TimeoutExpired:
                process.kill()
                print(f"✅ {name} 已强制终止")
        print("👋 所有服务已关闭")


def main():
    parser = argparse.ArgumentParser(
        description="反诈预警专家工作流 - 统一启动脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_system.py                    # 启动所有服务（默认端口）
  python run_system.py --multimodal-port 9000  # 指定多模态服务端口
  python run_system.py --langgraph-port 6000   # 指定 LangGraph 服务端口
  python run_system.py --check            # 仅检查环境
  python run_system.py --flow             # 运行完整工作流测试
  python run_system.py --node multimodal_input -i '{"input_text":"你好"}'  # 运行单个节点
        """
    )
    
    parser.add_argument(
        "--multimodal-port", 
        type=int, 
        default=8000,
        help="多模态处理服务端口 (默认：8000)"
    )
    
    parser.add_argument(
        "--langgraph-port", 
        type=int, 
        default=5000,
        help="LangGraph 主服务器端口 (默认：5000)"
    )
    
    parser.add_argument(
        "--check", 
        action="store_true",
        help="仅检查环境，不启动服务"
    )
    
    parser.add_argument(
        "--flow",
        action="store_true",
        help="运行完整工作流测试模式"
    )
    
    parser.add_argument(
        "--node",
        type=str,
        help="运行指定节点（需要提供节点 ID）"
    )
    
    parser.add_argument(
        "-i", "--input",
        type=str,
        default="",
        help="节点或工作流的输入数据（JSON 格式）"
    )
    
    args = parser.parse_args()
    
    # 仅检查环境
    if args.check:
        if check_environment():
            print("\n✅ 环境检查通过")
            sys.exit(0)
        else:
            sys.exit(1)
    
    # 运行测试模式
    if args.flow:
        run_single_mode("flow", input_data=args.input or '{"input_text": "你好，我收到了一个可疑链接"}')
        return
    
    if args.node:
        run_single_mode("node", node_id=args.node, input_data=args.input or '{"input_text": "你好"}')
        return
    
    # 启动所有服务
    start_all_services(
        multimodal_port=args.multimodal_port,
        langgraph_port=args.langgraph_port
    )


if __name__ == "__main__":
    main()
