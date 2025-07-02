# sanitize_readme.py
import re

input_path = "README.md"
output_path = "README_sanitized.md"

with open(input_path, "r", encoding="utf-8") as f:
    content = f.read()

# 기관명 (도메인) → 기관A~Z (example.org~z.org) 로 대체
org_names = re.findall(r'\d+\.\s(.+?)\s\((.*?)\)', content)
for idx, (org, domain) in enumerate(org_names):
    replacement = f"기관{chr(ord('A') + idx)} (example{idx+1}.org)"
    content = content.replace(f"{org} ({domain})", replacement)

# URL 도메인 마스킹
content = re.sub(r'https://[a-zA-Z0-9\.-]+', 'https://demo.example.com', content)

with open(output_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"✅ 저장 완료: {output_path}")
