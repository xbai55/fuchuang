import requests
import json
import time

# 配置信息
API_URL = "http://127.0.0.1:8002/api/v1/analyze_video_ocr_parallel"
VIDEO_PATH = r"C:\Users\xbai55\Desktop\fc\fuchuang\fuchuang\multimodal_input\test2.mp4"

def test_multimodal_analysis():
    print(f"🚀 开始测试多模态并行处理接口...")
    print(f"📹 正在读取视频文件: {VIDEO_PATH}")
    
    start_time = time.time()
    
    try:
        # 以二进制流形式打开视频文件
        with open(VIDEO_PATH, "rb") as f:
            files = {"file": ("test0.mp4", f, "video/mp4")}
            
            print("⏳ 正在发送请求到 8002 端口 (包含抽帧、鉴伪、OCR)...")
            response = requests.post(API_URL, files=files)
            
        # 处理结果
        if response.status_code == 200:
            result = response.json()
            print("\n✅ 测试成功！返回值如下：")
            print("-" * 50)
            print(f"任务 ID: {result.get('task_id')}")
            print(f"总耗时: {result.get('cost_time')}")
            
            data = result.get('data', {})
            print(f"🔥 是否为伪造视频: {data.get('is_fake_alert')}")
            print(f"📊 伪造概率: {data.get('fake_probability')}")
            print(f"📂 关键帧保存路径: {data.get('keyframe_dir')}")
            
            print("\n🤖 MLLM 提示词样例 (Payload):")
            print(data.get('mllm_payload'))
            print("-" * 50)
        else:
            print(f"\n❌ 测试失败，状态码: {response.status_code}")
            print(f"错误详情: {response.text}")

    except FileNotFoundError:
        print(f"❌ 错误：找不到文件 {VIDEO_PATH}，请确认路径是否正确。")
    except Exception as e:
        print(f"❌ 发生异常: {e}")
    
    end_time = time.time()
    print(f"\n⏱️ 脚本执行完毕，总用时: {end_time - start_time:.2f}s")

if __name__ == "__main__":
    test_multimodal_analysis()