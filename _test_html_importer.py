import sys
sys.path.insert(0, '.')
from rag.src.fraud_rag.html_importer import parse_html_content

html = '<html><body><h1>投资诈骗案例</h1><p>被告人利用网络平台实施诈骗，骗取被害人投资款项。</p></body></html>'
docs = parse_html_content(html, source_url='http://test.example.com/case1.html')
assert docs, "No documents returned"
d = docs[0]
print('category:', d.category)
print('tags:', d.tags[:3])
print('subtype:', d.subtype)
print('title:', d.title)
print('OK')
