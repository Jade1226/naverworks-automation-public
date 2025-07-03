import os
import pandas as pd
from glob import glob
import numpy as np
import re

# 서비스(표구조) → 실제 엑셀 파일 prefix 매핑 예시
파일prefix매핑 = {
    "계정": "계정",
    "액티브 유저": "액티브 유저",
    "공용용량": "공용용량",
    "게시판": "게시판",
    "메시지": "메시지",
    "메일": "메일",
    "캘린더": "캘린더",
    "주소록_외부연락처": "주소록_외부연락처",
    "주소록_그룹": "주소록_그룹",
    "설문": "설문",
    "할 일": "할 일",
}

# 구분(표구조) → 실제 시트명 매핑 예시
시트명매핑 = {
    "상태별 구성원 수": "상태별 구성원 수",
    "상태 별 구성원 수": "상태별 구성원 수",
    "앱 액티브 유저 수": "앱(App) 액티브 유저 수",
    "서비스별 용량": "서비스별 용량",
    "서비스 별 용량": "서비스별 용량",
    "연락처 사용 현황": "연락처 사용 현황",
    # 필요시 추가
}

# 항목(표구조) → 실제 컬럼명 매핑 예시
항목명매핑 = {
    # 상태 별 구성원 수
    "사용중": "사용중",  # 실제 컬럼명과 일치
    "일시 정지": "일시정지",
    "미접속": "접속대기",  # 표: 미접속, 실제: 접속대기
    "접속 대기": "접속대기",
    "삭제": "삭제",

    # 공용용량
    "사용 가능 용량": "사용 가능 용량",
    "사용 중 용량": "사용중 용량",  # 표: 사용 중 용량, 실제: 사용중 용량
    "게시판": "게시판",
    "메시지(노트 포함)": "메시지(노트 포함)",
    "캘린더": "캘린더",
    "설문": "설문",
    "템플릿": "템플릿",
    "할 일": "할 일",

    # 메시지
    "Bot": "Bot",  # 실제 컬럼명이 Bot인지 BOT인지 확인 필요
    "스티커/이모티콘": "스티커/이모티콘",
    "텍스트": "텍스트",
    "파일": "파일",
}

# 기관 그룹 분리
특이기관 = [
    "한국청소년정책연구원",
    "한국행정연구원"
]
일반기관 = [
    "한국조세재정연구원", "한국여성정책연구원", "한국법제연구원", "한국교육개발원",
    "한국개발연구원", "통일연구원", "육아정책연구소", "에너지경제연구원",
    "대외경제정책연구원", "과학기술정책연구원"
]

기관별_상태별구성원수_항목 = {
    "특이": ["사용중", "일시 정지", "접속 대기", "삭제"],
    "일반": ["사용중", "일시 정지", "미접속", "삭제"]
}

def get_상태별구성원수_항목(기관명):
    if 기관명 in 특이기관:
        return 기관별_상태별구성원수_항목["특이"]
    else:
        return 기관별_상태별구성원수_항목["일반"]

# 표 구조 동적 생성 함수
def make_표구조(기관명):
    return [
        ("계정", "구성원 수", ["총 구성원"]),
        ("계정", "상태 별 구성원 수", get_상태별구성원수_항목(기관명)),
        ("액티브 유저", "액티브 유저 수", ["액티브 유저 수"]),
        ("액티브 유저", "앱 액티브 유저 수", ["앱(App) 액티브 유저 수"]),
        ("공용용량", "사용 현황", ["사용중 용량", "사용 가능 용량", "사용률(%)"]),
        ("공용용량", "서비스별 용량", ["게시판", "템플릿", "메시지(노트 포함)", "캘린더", "설문", "할 일"]),
        ("게시판", "게시물 등록 수", ["게시물 등록 수"]),
        ("게시판", "게시물 읽음 수", ["게시물 읽음 수"]),
        ("메시지", "메시지 수", ["텍스트", "스티커/이모티콘", "Bot", "파일"]),
        ("메일", "보낸 메일 수", ["외부 메일", "내부 메일"]),
        ("메일", "받은 메일 수", ["외부 메일", "내부 메일"]),
        ("캘린더", "일정 등록 수", ["일정 등록 수"]),
        ("주소록_외부연락처", "외부연락처", ["일반 연락처"]),
        ("주소록_그룹", "그룹 수", ["그룹 수"]),
        ("설문", "설문 생성 수", ["설문 생성 수"]),
        ("할 일", "할 일", ["할 일 수"]),
    ]

def find_latest_file(stat_dir, prefix):
    files = glob(os.path.join(stat_dir, f"{prefix}*.xlsx"))
    if not files:
        return None
    return max(files, key=os.path.getctime)

def extract_min_max_with_unit(series):
    # 예: "21.3 GB", "360.5 KB", "0 B", "1.6 %"
    values = []
    for v in series.dropna():
        if isinstance(v, str):
            m = re.match(r'([\d\.]+)\s*([A-Za-z%]+)', v)
            if m:
                num = float(m.group(1))
                unit = m.group(2)
                values.append((num, unit, v))
        elif isinstance(v, (int, float)):
            values.append((v, '', str(v)))
    if not values:
        return '', ''
    from collections import Counter
    unit_counter = Counter([unit for _, unit, _ in values])
    main_unit = unit_counter.most_common(1)[0][0]
    filtered = [t for t in values if t[1] == main_unit]
    min_val = min(filtered, key=lambda x: x[0])
    max_val = max(filtered, key=lambda x: x[0])
    return min_val[2], max_val[2]

def extract_min_max(report_dir, org_name, 표구조):
    stat_dir = os.path.join(report_dir, org_name, "통계")
    result_rows = []
    for 서비스, 구분, 항목리스트 in 표구조:
        prefix = 파일prefix매핑.get(서비스, 서비스)
        file_path = find_latest_file(stat_dir, prefix)
        if not file_path or not os.path.exists(file_path):
            continue
        try:
            xls = pd.ExcelFile(file_path)
            sheet_name = 시트명매핑.get(구분, 구분)
            if sheet_name not in xls.sheet_names:
                continue
            df = pd.read_excel(xls, sheet_name)
            if not isinstance(df, pd.DataFrame):
                continue
            for 항목 in 항목리스트:
                col_name = 항목명매핑.get(항목, 항목)
                print(f"[DEBUG] 서비스={서비스}, 구분={구분}, 항목={항목}, col_name={col_name}, 컬럼존재={col_name in df.columns}")
                if col_name not in df.columns:
                    continue
                값시리즈 = df[col_name]
                print(f"[DEBUG] 값시리즈(앞 5개)={값시리즈.head().tolist() if hasattr(값시리즈, 'head') else 값시리즈}")
                # 단위가 포함된 문자열이 있는 경우 단위까지 포함해서 min/max 추출
                if any(isinstance(x, str) and re.search(r'[A-Za-z%]', x) for x in 값시리즈.dropna()):
                    최소, 최대 = extract_min_max_with_unit(값시리즈)
                    print(f"[DEBUG] 단위포함 최소={최소}, 최대={최대}")
                    if 최소 != '' and 최대 != '':
                        result_rows.append([서비스, 구분, 항목, 최소, 최대])
                else:
                    값시리즈 = pd.to_numeric(값시리즈, errors='coerce')
                    if isinstance(값시리즈, pd.Series):
                        값시리즈 = 값시리즈.dropna()
                        print(f"[DEBUG] 숫자변환 후 값시리즈(앞 5개)={값시리즈.head().tolist() if hasattr(값시리즈, 'head') else 값시리즈}")
                        if len(값시리즈) > 0:
                            최소 = 값시리즈.min()
                            최대 = 값시리즈.max()
                            print(f"[DEBUG] 숫자 최소={최소}, 최대={최대}")
                            result_rows.append([서비스, 구분, 항목, 최소, 최대])
                    else:
                        if pd.notna(값시리즈):
                            최소 = 최대 = 값시리즈
                            print(f"[DEBUG] 단일값 최소/최대={최소}")
                            result_rows.append([서비스, 구분, 항목, 최소, 최대])
        except Exception as e:
            print(f"{file_path} 처리 중 오류: {e}")
    # 결과 DataFrame
    result_df = pd.DataFrame(result_rows, columns=["서비스", "구분", "항목", "최소", "최대"])
    save_path = os.path.join(report_dir, org_name, f"{org_name}_통계.xlsx")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)  # 폴더가 없으면 생성
    result_df.to_excel(save_path, index=False)
    print(f"통합 통계 파일 저장 완료: {save_path}")

# 사용 예시
if __name__ == "__main__":
    report_dir = "downloads"
    for 기관명 in os.listdir(report_dir):
        기관경로 = os.path.join(report_dir, 기관명)
        if os.path.isdir(기관경로):
            print(f"=== {기관명} 처리 중 ===")
            표구조 = make_표구조(기관명)
            extract_min_max(report_dir, 기관명, 표구조) 