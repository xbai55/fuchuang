import smtplib
from email.mime.text import MIMEText

# 发件人
sender = "2036689220@qq.com"
password = "xtdqjalxubxgdihc"

# 收件人（可以就是你自己）
receiver = "3471383309@qq.com"

# 邮件内容
subject = "【天枢明御】诈骗预警通知"
content = """
检测到高风险诈骗行为！

风险类型：冒充警察要求转账
风险等级：高危

请立即停止操作，不要转账！
"""

msg = MIMEText(content, "plain", "utf-8")
msg["Subject"] = subject
msg["From"] = sender
msg["To"] = receiver

# 发送
try:
    smtp = smtplib.SMTP_SSL("smtp.qq.com", 465)
    smtp.login(sender, password)
    smtp.sendmail(sender, receiver, msg.as_string())
    smtp.quit()
    print("✅ 邮件发送成功")
except Exception as e:
    print("❌ 发送失败：", e)