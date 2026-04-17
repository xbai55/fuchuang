# scripts/test_rag_simple.py
import sys
import os

# 确保能找到 src 目录
sys.path.insert(0, os.path.abspath("src"))

try:
    from rag.local_rag import get_local_rag
    
    print("--- 正在初始化 Local RAG ---")
    # 这里会自动读取 backend/fraud_detection.db
    rag = get_local_rag()
    
    query = "公安局洗钱转账"
    print(f"查询词: {query}")
    
    cases, legal = rag.search(query)
    
    print(f"\n[结果] 检索到 {len(cases)} 条本地案例")
    for i, c in enumerate(cases):
        print(f"  案例 {i+1}: {c[:60]}...")
        
    print(f"\n[法律依据]: {legal}")

except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()