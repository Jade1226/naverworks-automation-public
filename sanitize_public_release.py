import re
import os

def sanitize_accounts(input_path="naverworks_accounts.py", output_path="naverworks_accounts_sanitized.py"):
    if not os.path.exists(input_path):
        print(f"❌ 파일 없음: {input_path}")
        return False

    with open(input_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    anon_lines = []
    org_count = 1
    for line in lines:
        if re.search(r'"[^"]+\s\([^)]+\)"', line):
            line = re.sub(r'"[^"]+\s\([^)]+\)"', f'"기관{org_count} (example{org_count}.org)"', line)
            org_count += 1
        anon_lines.append(line)

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(anon_lines)

    print(f"✅ 계정 설정 파일 가명화 완료 → {output_path}")
    return True

def sanitize_readme(input_path="README.md", output_path="README_sanitized.md"):
    if not os.path.exists(input_path):
        print(f"❌ 파일 없음: {input_path}")
        return False

    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    org_matches = re.findall(r'\d+\.\s(.+?)\s\((.*?)\)', content)
    for idx, (org, domain) in enumerate(org_matches):
        replacement = f"기관{chr(ord('A') + idx)} (example{idx+1}.org)"
        content = content.replace(f"{org} ({domain})", replacement)

    content = re.sub(r'https://[a-zA-Z0-9\.\-]+', 'https://demo.example.com', content)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ README 파일 마스킹 완료 → {output_path}")
    return True

def main():
    print("🚀 NAVER WORKS 공개용 파일 가명화/마스킹 시작")

    acc_success = sanitize_accounts()
    readme_success = sanitize_readme()

    if acc_success and readme_success:
        print("🎉 모든 작업이 완료되었습니다!")
    else:
        print("⚠️ 일부 파일에서 오류가 발생했습니다.")

if __name__ == "__main__":
    main()
