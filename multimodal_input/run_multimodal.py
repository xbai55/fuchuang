import argparse
import subprocess
import sys
import os
from typing import Dict, Callable
from pathlib import Path


def run_command(cmd: str, description: str):
    """运行命令并处理错误"""
    print(f"正在启动 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"启动 {description} 失败: {e}")
        return False


def start_audio_service(port: int = 8000):
    """启动音频处理服务"""
    cmd = f"cd audio_module && python main.py --port {port}"
    return run_command(cmd, f"音频服务 (端口 {port})")


def start_video_service(port: int = 8001):
    """启动视频处理服务"""
    cmd = f"cd video_module && python main.py --port {port}"
    return run_command(cmd, f"视频服务 (端口 {port})")


def start_ocr_service(port: int = 8002):
    """启动OCR处理服务"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 根据操作系统设置环境变量
    if os.name == 'nt':  # Windows
        cmd = f"cd /d {current_dir} && set PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True&& python ocr/main.py"
    else:  # Unix/Linux/macOS
        cmd = f"cd {current_dir} && PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True python ocr/main.py"
    return run_command(cmd, f"OCR服务 (端口 {port})")


def start_unified_service(port: int = 8000):
    """启动统一的多模态处理服务"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 根据操作系统设置环境变量
    if os.name == 'nt':  # Windows
        cmd = f"cd /d {current_dir} && set PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True&& python main.py --port {port}"
    else:  # Unix/Linux/macOS
        cmd = f"cd {current_dir} && PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True python main.py --port {port}"
    return run_command(cmd, f"统一多模态服务 (端口 {port})")


def check_model_weights():
    """检查必要的模型权重文件是否存在"""
    required_weights = [
        ("./audio_module/weights/latest_best_audio_model.pth", "音频深度伪造检测模型"),
        ("./video_module/weights/final_model.pth", "视频深度伪造检测模型"),
    ]
    
    missing_weights = []
    for weight_path, description in required_weights:
        if not os.path.exists(weight_path):
            missing_weights.append((weight_path, description))
    
    if missing_weights:
        print("\n⚠️  警告：以下模型权重文件缺失：")
        for path, desc in missing_weights:
            print(f"   - {desc}: {path}")
        print("   服务仍会启动，但对应功能将不可用\n")
        return False
    
    print("✅ 所有模型权重文件均已找到")
    return True


def start_all_services():
    """启动所有服务（在不同进程中）"""
    print("正在启动所有多模态服务...")
    
    # 检查模型权重
    check_model_weights()
    
    # 定义服务配置
    services = [
        ("audio_module.main:app", "音频服务", 8000),
        ("video_module.main:app", "视频服务", 8001),
        ("ocr.main:app", "OCR服务", 8002),
    ]
    
    processes = []
    for module, name, port in services:
        cmd = f"uvicorn {module} --host 0.0.0.0 --port {port} --reload"
        print(f"启动 {name} 在端口 {port}...")
        try:
            process = subprocess.Popen(cmd.split())
            processes.append((name, process))
        except Exception as e:
            print(f"启动 {name} 失败: {e}")
    
    print("\n所有服务已启动！")
    print("音频服务: http://localhost:8000")
    print("视频服务: http://localhost:8001") 
    print("OCR服务: http://localhost:8002")
    print("\n按 Ctrl+C 停止所有服务")
    
    try:
        for _, process in processes:
            process.wait()
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        for name, process in processes:
            try:
                process.terminate()
                process.wait(timeout=5)
                print(f"{name} 已停止")
            except subprocess.TimeoutExpired:
                process.kill()
                print(f"{name} 已强制终止")


class MultimodalServiceManager:
    """多模态服务管理器，为LangGraph集成准备"""
    
    def __init__(self):
        self.services = {
            'audio': {
                'name': 'Audio Service',
                'endpoint': '/api/v1/analyze_audio_for_mllm',
                'port': 8000,
                'handler': start_audio_service
            },
            'video': {
                'name': 'Video Service', 
                'endpoint': '/api/v1/analyze_video_for_mllm',
                'port': 8001,
                'handler': start_video_service
            },
            'ocr': {
                'name': 'OCR Service',
                'endpoint': '/api/v1/ocr_analyze_keyframes',
                'port': 8002, 
                'handler': start_ocr_service
            },
            'unified': {
                'name': 'Unified Service',
                'endpoint': '/api/v1/analyze_multimodal',
                'port': 8000,
                'handler': start_unified_service
            }
        }
    
    def get_service_config(self, service_type: str) -> Dict:
        """获取指定服务的配置"""
        if service_type not in self.services:
            raise ValueError(f"Unknown service type: {service_type}")
        return self.services[service_type]
    
    def get_all_services(self) -> Dict:
        """获取所有服务配置"""
        return self.services
    
    def start_service(self, service_type: str):
        """启动指定服务"""
        config = self.get_service_config(service_type)
        handler = config['handler']
        port = config['port']
        return handler(port)
    
    def get_api_endpoint(self, service_type: str) -> str:
        """获取API端点URL"""
        config = self.get_service_config(service_type)
        port = config['port']
        endpoint = config['endpoint']
        return f"http://localhost:{port}{endpoint}"


def main():
    parser = argparse.ArgumentParser(description="多模态输入服务启动器")
    parser.add_argument(
        "service", 
        nargs="?",
        choices=["audio", "video", "ocr", "unified", "all", "check"],
        default="unified",
        help="要启动的服务类型 (默认: unified)"
    )
    parser.add_argument("--port", type=int, help="指定端口 (仅对单个服务有效)")
    
    args = parser.parse_args()
    
    manager = MultimodalServiceManager()
    
    if args.service == "check":
        check_model_weights()
        return
    
    print(f"启动 {args.service} 服务...")
    
    if args.service == "all":
        start_all_services()
    elif args.service in ["audio", "video", "ocr", "unified"]:
        success = manager.start_service(args.service)
        if success:
            endpoint_url = manager.get_api_endpoint(args.service)
            print(f"✅ {manager.get_service_config(args.service)['name']} 启动成功!")
            print(f"📝 API 端点: {endpoint_url}")
            print(f"🔧 服务将在前台运行，按 Ctrl+C 停止")
        else:
            print(f"❌ 启动 {args.service} 服务失败")
            sys.exit(1)
    else:
        print(f"未知服务类型: {args.service}")
        sys.exit(1)


if __name__ == "__main__":
    main()