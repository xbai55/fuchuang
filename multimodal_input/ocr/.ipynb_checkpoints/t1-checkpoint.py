import time
import os
from paddleocr import PaddleOCRVL

# 确保输出目录存在
os.makedirs("output_local", exist_ok=True)

print("="*30)
print("开始执行 PaddleOCR VL 详细耗时测试")
print("="*30)

# ---------------------------------------------------------
# 阶段 1: 模型初始化耗时
# ---------------------------------------------------------
print("\n[1] 正在加载模型 (PaddleOCRVL 初始化)...")
start_init = time.perf_counter()  # 高精度计时开始
pipeline = PaddleOCRVL()
end_init = time.perf_counter()    # 高精度计时结束

init_time = end_init - start_init
print(f"    -> 模型初始化完成，耗时: {init_time:.4f} 秒")

# ---------------------------------------------------------
# 阶段 2: 纯推理耗时 (核心性能指标)
# ---------------------------------------------------------
image_path = "ocr"
print(f"\n[2] 正在对图片进行推理: {image_path}")

start_infer = time.perf_counter()
output = pipeline.predict(image_path)
end_infer = time.perf_counter()

infer_time = end_infer - start_infer
print(f"    -> 推理完成，耗时: {infer_time:.4f} 秒")
print(f"    -> 检测到 {len(output)} 个结果对象")

# ---------------------------------------------------------
# 阶段 3: 结果处理与保存耗时 (IO 密集型)
# ---------------------------------------------------------
print("\n[3] 正在处理并保存结果 (Print/JSON/Markdown)...")
start_io = time.perf_counter()

for i, res in enumerate(output):
    # 模拟打印 (如果结果非常多，print 本身也会耗时)
    # res.print() 
    
    # 保存 JSON
    json_path = f"output_local/result_{i}.json"
    res.save_to_json(save_path=json_path)
    
    # 保存 Markdown
    md_path = f"output_local/result_{i}.md"
    res.save_to_markdown(save_path=md_path)

end_io = time.perf_counter()
io_time = end_io - start_io
print(f"    -> 结果保存完成，耗时: {io_time:.4f} 秒")

# ---------------------------------------------------------
# 总结报告
# ---------------------------------------------------------
total_time = init_time + infer_time + io_time

print("\n" + "="*30)
print("⏱️  详细耗时统计报告")
print("="*30)
print(f"1. 模型初始化时间 : {init_time:>8.4f} 秒  ({(init_time/total_time)*100:.1f}%)")
print(f"2. 纯推理计算时间 : {infer_time:>8.4f} 秒  ({(infer_time/total_time)*100:.1f}%)")
print(f"3. 结果保存 IO 时间 : {io_time:>8.4f} 秒  ({(io_time/total_time)*100:.1f}%)")
print("-" * 30)
print(f"总计耗时          : {total_time:>8.4f} 秒")
print("="*30)

# 💡 额外提示：如果是批量处理，建议忽略第一次的初始化时间
print("\n[提示] 如果是批量处理图片，后续图片的平均耗时应参考 '纯推理计算时间'。")