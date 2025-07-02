# anonymize_accounts.py
import re

input_path = "naverworks_accounts.py"
output_path = "naverworks_accounts_sanitized.py"

with open(input_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

anon_lines = []
org_count = 1
for line in lines:
    if re.search(r'\(.*?\)', line):  # 도메인이 있는 계정 라인
        line = re.sub(r'"[^"]+\s\([^)]+\)"', f'"기관{org_count} (example{org_count}.org)"', line)
        org_count += 1
    anon_lines.append(line)

with open(output_path, "w", encoding="utf-8") as f:
    f.writelines(anon_lines)

print(f"✅ 저장 완료: {output_path}")