import os
import pickle
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from selenium import webdriver
from typing import Optional
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from naverworks_accounts import ACCOUNTS, TARGET_PAGES
from selenium.webdriver.remote.webelement import WebElement
import re

# selectors_organized.txt 파싱 함수
def parse_selectors_organized(filepath="selectors_organized.txt"):
    """정리된 셀렉터 파일을 파싱하여 PAGE_SELECTORS 딕셔너리를 생성"""
    PAGE_SELECTORS = {}
    current_section = None
    
    with open(filepath, encoding="utf-8") as f:
        lines = [line.rstrip() for line in f]
    
    for line in lines:
        line = line.strip()
        
        # 섹션 시작 확인 [섹션명]
        if line.startswith('[') and line.endswith(']'):
            current_section = line[1:-1]  # [ ] 제거
            PAGE_SELECTORS[current_section] = {}
            continue
        
        # 주석이나 빈 줄 무시
        if not line or line.startswith('#'):
            continue
        
        # 키=값 형태의 셀렉터 파싱
        if '=' in line and current_section:
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            PAGE_SELECTORS[current_section][key] = value
    
    return PAGE_SELECTORS

# 정리된 셀렉터 파일 파싱
PAGE_SELECTORS = parse_selectors_organized()

# 안전한 입력 함수
def safe_input(prompt: str) -> str:
    while True:
        value = input(prompt)
        if value.strip():
            return value
        print("값을 입력해주세요.")

# localStorage/sessionStorage 저장
def save_storage(driver, account_name):
    try:
        local = driver.execute_script("return JSON.stringify(window.localStorage);")
        with open(f"cookies/{account_name}_localstorage.json", "w", encoding="utf-8") as f:
            f.write(local)
    except Exception:
        pass
    try:
        session = driver.execute_script("return JSON.stringify(window.sessionStorage);")
        with open(f"cookies/{account_name}_sessionstorage.json", "w", encoding="utf-8") as f:
            f.write(session)
    except Exception:
        pass

# localStorage/sessionStorage 복원
def load_storage(driver, account_name):
    try:
        with open(f"cookies/{account_name}_localstorage.json", "r", encoding="utf-8") as f:
            local = f.read()
        driver.execute_script(
            "var items = JSON.parse(arguments[0]); for (var key in items) { window.localStorage.setItem(key, items[key]); }",
            local)
    except Exception:
        pass
    try:
        with open(f"cookies/{account_name}_sessionstorage.json", "r", encoding="utf-8") as f:
            session = f.read()
        driver.execute_script(
            "var items = JSON.parse(arguments[0]); for (var key in items) { window.sessionStorage.setItem(key, items[key]); }",
            session)
    except Exception:
        pass

# 달력 UI 클릭 기반 날짜 선택 함수
def set_calendar_date_by_click(driver, wait, selectors, target_date, which):
    """달력 UI에서 날짜를 클릭하여 선택 (입력 필드 value 확인 포함)"""
    # 입력 필드 클릭
    input_selector = selectors.get(f"{which}_date_input") or selectors.get("start_date_input")
    if not input_selector:
        print(f"[자동화] {which} 날짜 입력 필드 셀렉터가 없습니다.")
        return
    print(f"[자동화] {which} 날짜 입력 필드 클릭 중...")
    input_elem = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, input_selector)))
    input_elem.click()
    time.sleep(1)
    
    # 달력 헤더, 이동 버튼, 날짜 셀 셀렉터
    cal_header = selectors.get(f"{which}_calendar_header") or selectors.get("start_calendar_header")
    prev_year_btn = selectors.get(f"{which}_prev_year_btn") or selectors.get("start_prev_year_btn")
    next_year_btn = selectors.get(f"{which}_next_year_btn") or selectors.get("start_next_year_btn")
    prev_mon_btn = selectors.get(f"{which}_prev_mon_btn") or selectors.get("start_prev_mon_btn")
    next_mon_btn = selectors.get(f"{which}_next_mon_btn") or selectors.get("start_next_mon_btn")
    day_cell = selectors.get(f"{which}_day_cell") or selectors.get("start_day_cell")
    
    if not (cal_header and prev_year_btn and next_year_btn and prev_mon_btn and next_mon_btn and day_cell):
        print(f"[자동화] {which} 달력 셀렉터가 부족합니다.")
        return
    
    # 달력 연/월 맞추기
    try:
        # 현재 달력에 표시된 연/월 확인
        header_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, cal_header)))
        current_header = header_elem.text.strip()
        print(f"[자동화] 현재 달력 헤더: {current_header}")
        
        # 목표 연/월
        target_year = target_date.year
        target_month = target_date.month
        
        # 헤더에서 현재 연/월 파싱 (예: "2025년 6월" 또는 "2025. 6")
        year_match = re.search(r'(\d{4})', current_header)
        # 월 파싱 개선 - 다양한 형식 지원
        if '년' in current_header and '월' in current_header:
            # "2025년 6월" 형식
            month_match = re.search(r'년\s*(\d{1,2})\s*월', current_header)
        elif '.' in current_header:
            # "2025. 6" 형식
            parts = current_header.split('.')
            if len(parts) >= 2:
                month_match = re.search(r'(\d{1,2})', parts[1].strip())
        else:
            # 기타 형식
            month_match = re.search(r'(\d{1,2})', current_header)
        
        if year_match and month_match:
            current_year = int(year_match.group(1))
            current_month = int(month_match.group(1))
            
            print(f"[자동화] 현재: {current_year}년 {current_month}월, 목표: {target_year}년 {target_month}월")
            
            # 연도 맞추기
            while current_year < target_year:
                next_year_elem = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, next_year_btn)))
                next_year_elem.click()
                time.sleep(0.5)
                current_year += 1
                print(f"[자동화] 연도 이동: {current_year}년")
            
            while current_year > target_year:
                prev_year_elem = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, prev_year_btn)))
                prev_year_elem.click()
                time.sleep(0.5)
                current_year -= 1
                print(f"[자동화] 연도 이동: {current_year}년")
            
            # 월 맞추기
            while current_month < target_month:
                next_mon_elem = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, next_mon_btn)))
                next_mon_elem.click()
                time.sleep(0.5)
                current_month += 1
                print(f"[자동화] 월 이동: {current_month}월")
            
            while current_month > target_month:
                prev_mon_elem = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, prev_mon_btn)))
                prev_mon_elem.click()
                time.sleep(0.5)
                current_month -= 1
                print(f"[자동화] 월 이동: {current_month}월")
        else:
            print(f"[경고] 달력 헤더에서 연/월을 파싱할 수 없습니다: {current_header}")
            return False
            
    except Exception as e:
        print(f"[오류] 달력 연/월 맞추기 중 예외 발생: {e}")
        return False
    
    # 날짜 클릭
    try:
        day_cells = driver.find_elements(By.CSS_SELECTOR, day_cell)
        target_day = str(target_date.day)
        
        for cell in day_cells:
            try:
                # 이번 달 날짜인지 확인
                classes = cell.get_attribute("class") or ""
                if "calendar-prev-mon" in classes or "calendar-next-mon" in classes:
                    continue  # 이번 달이 아님
                
                # 날짜 텍스트 확인
                a_tag = cell.find_element(By.CSS_SELECTOR, "a.calendar-date")
                if a_tag.text.strip() == target_day:
                    a_tag.click()
                    print(f"[자동화] {target_day}일 클릭 완료")
                    time.sleep(0.5)
                    
                    # 날짜 클릭 후 value 확인
                    try:
                        value = input_elem.get_attribute("value")
                        target_str = target_date.strftime("%Y. %m. %d")
                        if value != target_str:
                            print(f"[경고] {which} 날짜 입력 필드 value가 원하는 값과 다릅니다: {value} (목표: {target_str})")
                        else:
                            print(f"[확인] {which} 날짜 입력 필드 value 정상: {value}")
                    except Exception as e:
                        print(f"[오류] {which} 날짜 입력 필드 value 확인 중 예외 발생: {e}")
                    
                    return True
            except Exception as e:
                continue
        
        print(f"[경고] 달력에서 {target_day}일을 찾을 수 없습니다.")
        return False
        
    except Exception as e:
        print(f"[오류] 달력 날짜 선택 중 예외 발생: {e}")
        return False

# 기존 set_calendar_date 함수를 클릭 기반으로 변경
def set_calendar_date(self, selectors, target_date, date_type="start"):
    """기존 함수를 클릭 기반으로 래핑"""
    return set_calendar_date_by_click(self.driver, self.wait, selectors, target_date, date_type)

class NaverWorksAutomation:
    def __init__(self):
        self.driver: Optional[WebDriver] = None
        self.wait: Optional[WebDriverWait] = None
        # self.setup_driver()  # 계정 선택 후에 실행하도록 변경
    
    def setup_driver(self):
        """Chrome 드라이버 설정"""
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 다운로드 설정
        prefs = {
            "download.default_directory": os.path.abspath("downloads"),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 15)
    
    def get_login_url(self, account_name: str) -> str:
        """계정명에 따른 로그인 URL 반환 (기관별 분기)"""
        if "kdi.re.kr" in account_name or "한국개발연구원" in account_name:
            return "https://mail.kdi.re.kr"
        elif "kiep.go.kr" in account_name or "대외경제정책연구원" in account_name:
            return "https://sso.kiep.go.kr/sso/user/login/view?agt_id=kiep-naver"
        else:
            return "https://dev.gov-naverworks.com/kr/console/openapi/v2/app/list/view"
    
    def save_login_cookie(self, account_name: str):
        """로그인 후 쿠키 저장"""
        assert self.driver is not None
        login_url = self.get_login_url(account_name)
        
        print(f"\n=== {account_name} 로그인 시작 ===")
        print(f"로그인 URL: {login_url}")
        
        # 로그인 페이지로 이동
        self.driver.get(login_url)
        self.driver.delete_all_cookies()
        
        print("\n수동으로 로그인 및 2차 인증을 완료해주세요.")
        print("완료 후 Enter를 눌러주세요...")
        input()
        
        # 실제 통계 첫 페이지로 이동 후 쿠키/스토리지 저장
        if TARGET_PAGES:
            self.driver.get(TARGET_PAGES[0][0])
            time.sleep(3)
        
        # 쿠키 저장
        cookies_dir = "cookies"
        os.makedirs(cookies_dir, exist_ok=True)
        
        cookies_file = os.path.join(cookies_dir, f"{account_name}.pkl")
        pickle.dump(self.driver.get_cookies(), open(cookies_file, "wb"))
        save_storage(self.driver, account_name)
        
        print(f"쿠키가 {cookies_file}에 저장되었습니다.")
    
    def load_cookie(self, account_name: str):
        """저장된 쿠키 로드"""
        assert self.driver is not None
        login_url = self.get_login_url(account_name)
        cookies_file = os.path.join("cookies", f"{account_name}.pkl")
        
        if not os.path.exists(cookies_file):
            print(f"쿠키 파일이 없습니다: {cookies_file}")
            return False
        
        # 로그인 페이지로 이동 후 쿠키 로드
        self.driver.get(login_url)
        self.driver.delete_all_cookies()
        
        cookies = pickle.load(open(cookies_file, "rb"))
        for cookie in cookies:
            try:
                self.driver.add_cookie(cookie)
            except Exception as e:
                print(f"쿠키 추가 실패: {e}")
        
        # 실제 통계 첫 페이지로 이동 후 새로고침
        if TARGET_PAGES:
            self.driver.get(TARGET_PAGES[0][0])
            time.sleep(2)
            self.driver.refresh()
            time.sleep(2)
        else:
            self.driver.refresh()
            time.sleep(2)
        
        # 로그인 성공 확인 (대시보드 또는 메뉴 요소 확인)
        try:
            # 여러 가능한 로그인 성공 지표 확인
            success_indicators = [
                ".dashboard",
                ".main-menu",
                ".user-info",
                ".logout-btn",
                "[data-testid='dashboard']"
            ]
            
            for indicator in success_indicators:
                try:
                    self.driver.find_element(By.CSS_SELECTOR, indicator)
                    print(f"{account_name} 로그인 성공")
                    return True
                except NoSuchElementException:
                    continue
            
            # URL 기반 확인
            current_url = self.driver.current_url
            if "login" not in current_url.lower() and "auth" not in current_url.lower():
                print(f"{account_name} 로그인 성공 (URL 기반)")
                return True
                
            print(f"{account_name} 로그인 실패")
            return False
            
        except Exception as e:
            print(f"로그인 확인 중 오류: {e}")
            return False
    
    def capture_graph(self, page_name: str, save_dir: str, graph_name: str = ""):
        """그래프 캡처"""
        assert self.driver is not None
        try:
            # 페이지별 셀렉터 가져오기
            selectors = self.get_selectors(page_name, graph_name)
            graph_element = None
            
            # 1. 먼저 PAGE_SELECTORS에서 그래프 셀렉터 찾기
            if selectors and selectors.get("graph"):
                try:
                    graph_element = self.driver.find_element(By.CSS_SELECTOR, selectors["graph"])
                    print(f"[DEBUG] PAGE_SELECTORS에서 그래프 요소 찾음: {selectors['graph']}")
                except NoSuchElementException:
                    print(f"[DEBUG] PAGE_SELECTORS 그래프 셀렉터 실패: {selectors['graph']}")
            
            # 2. 그래프 요소를 찾지 못한 경우 범용 셀렉터 시도
            if not graph_element:
                # 메일 페이지는 특별 처리
                if page_name == "메일":
                    graph_selectors = [
                        ".graph",
                        "div.graph",
                        "#root .graph",
                        ".chart-container",
                        ".chart"
                    ]
                else:
                    graph_selectors = [
                        ".graph",
                        "div.graph",
                        "#root .graph"
                    ]
                
                for selector in graph_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            # 가장 큰 그래프 요소 선택
                            graph_element = max(elements, key=lambda x: x.size['width'] * x.size['height'])
                            print(f"[DEBUG] 범용 셀렉터로 그래프 요소 찾음: {selector}")
                            break
                    except NoSuchElementException:
                        continue
            
            if not graph_element:
                print(f"그래프 요소를 찾을 수 없습니다: {page_name}")
                # 전체 페이지 캡처로 대체
                return self.capture_full_page(page_name, save_dir, graph_name)
            
            # 파일명 생성 (페이지명 포함)
            if graph_name:
                filename = f"{page_name}_{graph_name}.png"
            else:
                filename = f"{page_name}.png"
            
            filepath = os.path.join(save_dir, filename)
            
            # 그래프 요소를 화면에 보이도록 스크롤
            self.driver.execute_script("arguments[0].scrollIntoView(true);", graph_element)
            time.sleep(1)
            
            # 스크린샷 캡처
            graph_element.screenshot(filepath)
            
            # 파일이 실제로 생성되었는지 확인
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                print(f"그래프 캡처 완료: {filename} ({os.path.getsize(filepath)} bytes)")
                return True
            else:
                print(f"그래프 캡처 실패: 파일이 생성되지 않음 - {filename}")
                return self.capture_full_page(page_name, save_dir, graph_name)
            
        except Exception as e:
            print(f"그래프 캡처 중 오류: {e}")
            return self.capture_full_page(page_name, save_dir, graph_name)
    
    def capture_full_page(self, page_name: str, save_dir: str, graph_name: str = ""):
        """전체 페이지 캡처 (그래프 캡처 실패 시 대체)"""
        assert self.driver is not None
        try:
            if graph_name:
                filename = f"{page_name}_{graph_name}_full.png"
            else:
                filename = f"{page_name}_full.png"
            
            filepath = os.path.join(save_dir, filename)
            self.driver.save_screenshot(filepath)
            print(f"전체 페이지 캡처 완료: {filename}")
            return True
        except Exception as e:
            print(f"전체 페이지 캡처도 실패: {e}")
            return False
    
    def find_and_click_button(self, button_selectors: list, timeout: int = 10):
        """버튼 찾기 및 클릭"""
        assert self.driver is not None
        for selector in button_selectors:
            if not selector:  # None이나 빈 문자열 체크
                continue
            try:
                button = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                button.click()
                time.sleep(2)
                return True
            except TimeoutException:
                continue
        return False
    
    def get_selectors(self, page_name: str, tab_name: Optional[str] = None):
        """정리된 셀렉터에서 해당 페이지/탭의 셀렉터를 가져옴"""
        if tab_name:
            key = f"{page_name}_{tab_name}"
        else:
            key = page_name
        print(f"[DEBUG] get_selectors 호출: page_name={page_name}, tab_name={tab_name}, key={key}")
        selectors = PAGE_SELECTORS.get(key, {})
        if not selectors:
            print(f"[자동화] {key}에 대한 셀렉터를 찾을 수 없습니다.")
            return {}
        return selectors
    
    def get_download_selectors(self, page_name: str, tab_name: Optional[str] = None):
        """다운로드 버튼 셀렉터를 가져옴"""
        # 다운로드 전용 키 생성
        if tab_name:
            download_key = f"{page_name}_{tab_name}_다운로드"
        else:
            # 특수 케이스 처리
            if page_name == "할 일":
                download_key = "할일_다운로드"
            elif page_name == "액티브 유저":
                download_key = "액티브유저_다운로드"
            else:
                download_key = f"{page_name}_다운로드"
        
        print(f"[DEBUG] get_download_selectors 호출: page_name={page_name}, tab_name={tab_name}, key={download_key}")
        download_selectors = PAGE_SELECTORS.get(download_key, {})
        if not download_selectors:
            print(f"[경고] 다운로드 버튼 셀렉터가 없습니다: {page_name}")
            return {}
        return download_selectors

    def download_file(self, account_name: str, page_name: str):
        """엑셀 파일 다운로드 및 이동 (항상 downloads/기관명/통계 폴더에 저장)"""
        import shutil
        import glob
        
        # 엑셀 저장 경로
        save_dir = os.path.join("downloads", account_name, "통계")
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir, exist_ok=True)
                print(f"[DEBUG] 엑셀 저장 디렉토리 생성됨: {save_dir}")
            except Exception as e:
                print(f"[경고] 엑셀 저장 디렉토리 생성 실패: {e}")
                return
        else:
            print(f"[DEBUG] 엑셀 저장 디렉토리 이미 존재: {save_dir}")
        
        # downloads 폴더에서 최신 엑셀 파일 찾기
        downloads_dir = "downloads"
        if not os.path.exists(downloads_dir):
            print(f"[경고] downloads 폴더가 존재하지 않습니다: {downloads_dir}")
            try:
                os.makedirs(downloads_dir, exist_ok=True)
                print(f"[DEBUG] downloads 폴더 생성됨: {downloads_dir}")
            except Exception as e:
                print(f"[경고] downloads 폴더 생성 실패: {e}")
                return
        
        # 다운로드 완료까지 대기 (최대 15초)
        max_wait = 15
        wait_time = 0
        excel_files = []
        while wait_time < max_wait:
            try:
                excel_files = glob.glob(os.path.join(downloads_dir, "*.xlsx"))
                if excel_files:
                    valid_files = [f for f in excel_files if os.path.getsize(f) > 0 and not f.endswith('.tmp') and not f.endswith('.crdownload')]
                    if valid_files:
                        excel_files = valid_files
                        break
            except Exception as e:
                print(f"[DEBUG] 파일 검색 중 오류: {e}")
            time.sleep(1)
            wait_time += 1
            print(f"[DEBUG] 엑셀 파일 다운로드 대기 중... ({wait_time}/{max_wait})")
        if not excel_files:
            print(f"[경고] downloads 폴더에서 엑셀 파일을 찾을 수 없습니다: {downloads_dir}")
            try:
                all_files = os.listdir(downloads_dir)
                print(f"[DEBUG] downloads 폴더 내용: {all_files}")
            except Exception as e:
                print(f"[DEBUG] downloads 폴더 내용 확인 실패: {e}")
            return
        try:
            latest_file = max(excel_files, key=os.path.getctime)
            print(f"[DEBUG] 선택된 파일: {latest_file} (크기: {os.path.getsize(latest_file)} bytes)")
        except Exception as e:
            print(f"[경고] 최신 파일 선택 실패: {e}")
            latest_file = excel_files[0]
        filename = f"{page_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        target_path = os.path.join(save_dir, filename)
        print(f"[DEBUG] 다운로드 파일 정보:")
        print(f"[DEBUG] - 원본 파일: {latest_file}")
        print(f"[DEBUG] - 저장 디렉토리: {save_dir}")
        print(f"[DEBUG] - 대상 파일: {target_path}")
        try:
            shutil.move(latest_file, target_path)
            print(f"엑셀 파일 다운로드 완료: {filename} ({os.path.getsize(target_path)} bytes)")
        except Exception as e:
            print(f"엑셀 파일 이동 중 오류: {e}")
            try:
                shutil.copy2(latest_file, target_path)
                print(f"엑셀 파일 복사 완료: {filename}")
                try:
                    os.remove(latest_file)
                    print(f"[DEBUG] 원본 파일 삭제 완료: {latest_file}")
                except Exception as e2:
                    print(f"[DEBUG] 원본 파일 삭제 실패: {e2}")
            except Exception as e2:
                print(f"엑셀 파일 복사도 실패: {e2}")

    def process_dual_graph_page(self, page_name: str, save_dir: str, start_date: datetime, end_date: datetime, account_name: str):
        assert self.driver is not None
        assert self.wait is not None
        
        # 페이지별 탭명 정의
        tab_names = {
            "계정": ["구성원수", "상태별구성원수"],
            "액티브 유저": ["액티브유저수", "앱액티브유저수"],
            "공용용량": ["사용현황", "서비스별용량"],
            "게시판": ["게시물등록수", "게시물읽음수"]
        }
        
        tabs = tab_names.get(page_name, [])
        if len(tabs) < 2:
            print(f"페이지 {page_name}에 대한 탭 정보가 없습니다.")
            return
        
        # 첫 번째 그래프
        selectors1 = self.get_selectors(page_name, tabs[0])
        required_keys = ["start_date_input", "start_calendar_header", "start_day_cell", "start_prev_year_btn", "start_next_year_btn", "start_prev_mon_btn", "start_next_mon_btn"]
        if all(selectors1.get(k) for k in required_keys):
            set_calendar_date_by_click(self.driver, self.wait, selectors1, start_date, "start")
            set_calendar_date_by_click(self.driver, self.wait, selectors1, end_date, "end")
            if selectors1.get("search_button"):
                self.find_and_click_button([selectors1["search_button"]])
            time.sleep(3)
            self.capture_graph(page_name, save_dir, tabs[0])
        
        # 두 번째 그래프
        selectors2 = self.get_selectors(page_name, tabs[1])
        if all(selectors2.get(k) for k in required_keys):
            set_calendar_date_by_click(self.driver, self.wait, selectors2, start_date, "start")
            set_calendar_date_by_click(self.driver, self.wait, selectors2, end_date, "end")
            if selectors2.get("search_button"):
                self.find_and_click_button([selectors2["search_button"]])
            time.sleep(3)
            self.capture_graph(page_name, save_dir, tabs[1])
        
        # 다운로드 버튼
        download_selectors = self.get_download_selectors(page_name)
        download_btn = download_selectors.get("download_button")
        if download_btn:
            print(f"[DEBUG] 다운로드 버튼 클릭 시도: {download_btn}")
            if self.find_and_click_button([download_btn]):
                print(f"[DEBUG] 다운로드 버튼 클릭 성공")
                time.sleep(3)
                self.download_file(account_name, page_name)
            else:
                print(f"[경고] 다운로드 버튼 클릭 실패: {download_btn}")
        else:
            print(f"[경고] 다운로드 버튼 셀렉터가 없습니다: {page_name}")

    def process_single_graph_page(self, page_name: str, save_dir: str, start_date: datetime, end_date: datetime, account_name: str):
        assert self.driver is not None
        assert self.wait is not None
        selectors = self.get_selectors(page_name)
        required_keys = ["start_date_input", "start_calendar_header", "start_day_cell", "start_prev_year_btn", "start_next_year_btn", "start_prev_mon_btn", "start_next_mon_btn"]
        if all(selectors.get(k) for k in required_keys):
            set_calendar_date_by_click(self.driver, self.wait, selectors, start_date, "start")
            set_calendar_date_by_click(self.driver, self.wait, selectors, end_date, "end")
            if selectors.get("search_button"):
                self.find_and_click_button([selectors["search_button"]])
            time.sleep(3)
            self.capture_graph(page_name, save_dir)
        
        # 다운로드 버튼
        download_selectors = self.get_download_selectors(page_name)
        download_btn = download_selectors.get("download_button")
        if download_btn:
            print(f"[DEBUG] 다운로드 버튼 클릭 시도: {download_btn}")
            if self.find_and_click_button([download_btn]):
                print(f"[DEBUG] 다운로드 버튼 클릭 성공")
                time.sleep(3)
                self.download_file(account_name, page_name)
            else:
                print(f"[경고] 다운로드 버튼 클릭 실패: {download_btn}")
        else:
            print(f"[경고] 다운로드 버튼 셀렉터가 없습니다: {page_name}")

    def process_tab_graph_page(self, page_name: str, save_dir: str, start_date: datetime, end_date: datetime, account_name: str):
        assert self.driver is not None
        assert self.wait is not None
        tab_selectors = [
            ".tab-item",
            ".nav-tab",
            ".tab",
            ".chart-tab"
        ]
        tabs = []
        for selector in tab_selectors:
            try:
                tabs = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if tabs:
                    break
            except NoSuchElementException:
                continue
        if not tabs:
            print("탭을 찾을 수 없습니다.")
            return
        for tab in tabs:
            try:
                tab_name = tab.text.strip()
                if not tab_name:
                    continue
                tab.click()
                time.sleep(3)
                selectors = self.get_selectors(page_name, tab_name)
                required_keys = ["start_date_input", "start_calendar_header", "start_day_cell", "start_prev_year_btn", "start_next_year_btn", "start_prev_mon_btn", "start_next_mon_btn"]
                if all(selectors.get(k) for k in required_keys):
                    set_calendar_date_by_click(self.driver, self.wait, selectors, start_date, "start")
                    set_calendar_date_by_click(self.driver, self.wait, selectors, end_date, "end")
                    if selectors.get("search_button"):
                        self.find_and_click_button([selectors["search_button"]])
                    time.sleep(3)
                    self.capture_graph(page_name, save_dir, tab_name)
                    # 다운로드 버튼
                    download_selectors = self.get_download_selectors(page_name, tab_name)
                    download_btn = download_selectors.get("download_button")
                    if download_btn:
                        print(f"[DEBUG] 다운로드 버튼 클릭 시도: {download_btn}")
                        if self.find_and_click_button([download_btn]):
                            print(f"[DEBUG] 다운로드 버튼 클릭 성공")
                            time.sleep(3)
                            self.download_file(account_name, f"{page_name}_{tab_name}")
                        else:
                            print(f"[경고] 다운로드 버튼 클릭 실패: {download_btn}")
                    else:
                        print(f"[경고] 다운로드 버튼 셀렉터가 없습니다: {page_name}_{tab_name}")
            except Exception as e:
                print(f"탭 처리 중 오류: {e}")
                continue

    def process_address_page(self, save_dir: str, start_date: datetime, end_date: datetime, tab_name: str, account_name: str):
        assert self.driver is not None
        assert self.wait is not None
        selectors = self.get_selectors("주소록", tab_name)
        if not selectors:
            print(f"[자동화] 주소록_{tab_name}에 대한 셀렉터를 찾을 수 없습니다.")
            return
        # 탭 클릭
        tab_btn = selectors.get("tab")
        if tab_btn:
            self.find_and_click_button([tab_btn])
        time.sleep(1)
        # 날짜 입력 및 조회
        set_calendar_date_by_click(self.driver, self.wait, selectors, start_date, "start")
        set_calendar_date_by_click(self.driver, self.wait, selectors, end_date, "end")
        search_btn = selectors.get("search_button")
        if search_btn:
            self.find_and_click_button([search_btn])
        time.sleep(3)
        self.capture_graph("주소록", save_dir, tab_name)
        # 다운로드 버튼
        download_selectors = self.get_download_selectors("주소록", tab_name)
        download_btn = download_selectors.get("download_button")
        if download_btn:
            print(f"[DEBUG] 주소록 다운로드 버튼 클릭 시도: {download_btn}")
            if self.find_and_click_button([download_btn]):
                print(f"[DEBUG] 주소록 다운로드 버튼 클릭 성공")
                time.sleep(3)
                self.download_file(account_name, f"주소록_{tab_name}")
            else:
                print(f"[경고] 주소록 다운로드 버튼 클릭 실패: {download_btn}")
        else:
            print(f"[경고] 주소록 다운로드 버튼 셀렉터가 없습니다: {tab_name}")

    def process_account_page(self, account_name: str, page_url: str, page_name: str, start_date: datetime, end_date: datetime):
        """계정별 페이지 처리"""
        assert self.driver is not None
        print(f"\n--- {page_name} 페이지 처리 시작 ---")
        
        # 페이지 이동
        self.driver.get(page_url)
        time.sleep(5)
        
        # 저장 디렉토리 생성
        save_dir = os.path.join("downloads", account_name)
        os.makedirs(save_dir, exist_ok=True)
        
        # 페이지 타입별 처리
        if page_name == "계정":
            self.process_dual_graph_page(page_name, save_dir, start_date, end_date, account_name)
            
        elif page_name == "액티브 유저":
            self.process_dual_graph_page(page_name, save_dir, start_date, end_date, account_name)
            
        elif page_name == "공용용량":
            self.process_dual_graph_page(page_name, save_dir, start_date, end_date, account_name)
            
        elif page_name == "게시판":
            self.process_dual_graph_page(page_name, save_dir, start_date, end_date, account_name)
            
        elif page_name.startswith("주소록"):
            if page_name == "주소록_외부연락처":
                self.process_address_page(save_dir, start_date, end_date, "외부연락처", account_name)
            elif page_name == "주소록_그룹":
                self.process_address_page(save_dir, start_date, end_date, "그룹", account_name)
            else:
                self.process_tab_graph_page(page_name, save_dir, start_date, end_date, account_name)
            
        elif page_name == "메일":
            self.process_mail_page(save_dir, start_date, end_date, account_name)
            
        else:
            self.process_single_graph_page(page_name, save_dir, start_date, end_date, account_name)
    
    def process_mail_page(self, save_dir: str, start_date: datetime, end_date: datetime, account_name: str):
        assert self.driver is not None
        assert self.wait is not None
        
        # 저장 디렉토리 확인 및 생성
        print(f"[DEBUG] 메일 페이지 저장 디렉토리: {save_dir}")
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir, exist_ok=True)
                print(f"[DEBUG] 메일 페이지 저장 디렉토리 생성됨: {save_dir}")
            except Exception as e:
                print(f"[경고] 메일 페이지 저장 디렉토리 생성 실패: {e}")
                return
        
        # 보낸/받은 메일 수 각각 그래프 캡처 (key를 selectors_organized.txt와 정확히 일치시킴)
        for tab_name, file_label in [("보낸메일수", "보낸메일수"), ("받은메일수", "받은메일수")]:
            selectors = self.get_selectors("메일", tab_name)
            if not selectors:
                print(f"[자동화] 메일_{tab_name}에 대한 셀렉터를 찾을 수 없습니다.")
                continue
            set_calendar_date_by_click(self.driver, self.wait, selectors, start_date, "start")
            set_calendar_date_by_click(self.driver, self.wait, selectors, end_date, "end")
            search_btn = selectors.get("search_button")
            if search_btn:
                self.find_and_click_button([search_btn])
            time.sleep(3)

            # 그래프 캡처
            try:
                mail_graph_selectors = [
                    selectors.get("graph"),
                    "#root > div > div.container > div > div.contents_body > div > div > div.graph",
                    "div.graph",
                    ".graph",
                    ".chart-container",
                    ".chart",
                    "[class*='chart']",
                    "[class*='graph']",
                    "canvas",
                    ".recharts-wrapper"
                ]
                graph_element = None
                for selector in mail_graph_selectors:
                    if not selector:
                        continue
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            valid_elements = [elem for elem in elements if elem.size['width'] > 0 and elem.size['height'] > 0]
                            if valid_elements:
                                graph_element = max(valid_elements, key=lambda x: x.size['width'] * x.size['height'])
                                print(f"[DEBUG] 메일 그래프 요소 찾음: {selector} (크기: {graph_element.size})")
                                break
                    except Exception as e:
                        print(f"[DEBUG] 셀렉터 {selector} 시도 실패: {e}")
                        continue
                if graph_element:
                    filename = f"메일_{file_label}.png"
                    filepath = os.path.join(save_dir, filename)
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", graph_element)
                    time.sleep(2)
                    if graph_element.is_displayed() and graph_element.size['width'] > 0 and graph_element.size['height'] > 0:
                        try:
                            graph_element.screenshot(filepath)
                            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                                print(f"그래프 캡처 완료: {filename} ({os.path.getsize(filepath)} bytes)")
                            else:
                                print(f"그래프 캡처 실패: 파일이 생성되지 않음 - {filename}")
                                self.capture_full_page("메일", save_dir, file_label)
                        except Exception as e:
                            print(f"그래프 스크린샷 캡처 중 오류: {e}")
                            self.capture_full_page("메일", save_dir, file_label)
                    else:
                        print(f"그래프 요소가 화면에 표시되지 않음 (displayed: {graph_element.is_displayed()}, size: {graph_element.size})")
                        self.capture_full_page("메일", save_dir, file_label)
                else:
                    print("메일 그래프 요소를 찾을 수 없습니다.")
                    self.capture_full_page("메일", save_dir, file_label)
            except Exception as e:
                print(f"메일 그래프 캡처 중 오류: {e}")
                self.capture_full_page("메일", save_dir, file_label)

        # 다운로드 버튼 클릭 후 메뉴 클릭 (엑셀은 기존대로 한 번만)
        download_selectors = self.get_download_selectors("메일", "보낸/받은 메일 수")
        download_btn = download_selectors.get("download_button")
        if download_btn:
            print(f"[DEBUG] 메일 다운로드 버튼 클릭 시도: {download_btn}")
            try:
                download_button_selectors = [
                    download_btn,
                    "button.lw_btn_drop",
                    "#root > div > div.container > div > div.contents_head > div > div > button",
                    "button[class*='drop']",
                    "button[class*='download']"
                ]
                clicked = False
                for btn_selector in download_button_selectors:
                    try:
                        button = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, btn_selector))
                        )
                        button.click()
                        print(f"[DEBUG] 메일 다운로드 버튼 클릭 성공: {btn_selector}")
                        clicked = True
                        break
                    except Exception:
                        continue
                if clicked:
                    time.sleep(2)
                    try:
                        menu_selectors = [
                            "a[href*='보낸/받은 메일 수']",
                            "a:contains('보낸/받은 메일 수')",
                            "a",
                            "li a",
                            ".dropdown-menu a",
                            "[class*='menu'] a",
                            "[class*='dropdown'] a"
                        ]
                        menu_clicked = False
                        for menu_selector in menu_selectors:
                            try:
                                menu_elements = self.driver.find_elements(By.CSS_SELECTOR, menu_selector)
                                print(f"[DEBUG] 메뉴 셀렉터 {menu_selector}로 {len(menu_elements)}개 요소 찾음")
                                for element in menu_elements:
                                    try:
                                        element_text = element.text.strip()
                                        print(f"[DEBUG] 메뉴 요소 텍스트: '{element_text}'")
                                        if "보낸/받은 메일 수" in element_text:
                                            if element.is_displayed() and element.is_enabled():
                                                element.click()
                                                print(f"[DEBUG] 메일 다운로드 메뉴 클릭 성공: '{element_text}'")
                                                menu_clicked = True
                                                time.sleep(3)
                                                self.download_file(account_name, "메일_보낸받은메일수")
                                                break
                                            else:
                                                print(f"[DEBUG] 메뉴 요소가 클릭 불가능: displayed={element.is_displayed()}, enabled={element.is_enabled()}")
                                    except Exception as e:
                                        print(f"[DEBUG] 메뉴 요소 처리 중 오류: {e}")
                                        continue
                                if menu_clicked:
                                    break
                            except Exception as e:
                                print(f"[DEBUG] 메뉴 셀렉터 {menu_selector} 처리 중 오류: {e}")
                                continue
                        if not menu_clicked:
                            print(f"[경고] 메일 다운로드 메뉴를 찾을 수 없습니다")
                            try:
                                page_text = self.driver.page_source
                                if "보낸/받은 메일 수" in page_text:
                                    print(f"[DEBUG] 페이지에 '보낸/받은 메일 수' 텍스트가 존재함")
                                else:
                                    print(f"[DEBUG] 페이지에 '보낸/받은 메일 수' 텍스트가 없음")
                            except Exception as e:
                                print(f"[DEBUG] 페이지 텍스트 검색 실패: {e}")
                    except Exception as e:
                        print(f"[경고] 메일 다운로드 메뉴 클릭 실패: {e}")
                else:
                    print(f"[경고] 메일 다운로드 버튼 클릭 실패")
            except Exception as e:
                print(f"[경고] 메일 다운로드 버튼 클릭 실패: {e}")
        else:
            print(f"[경고] 메일 다운로드 버튼 셀렉터가 없습니다")

    def main(self):
        """메인 실행 함수"""
        try:
            print("=== NAVER WORKS 통계 페이지 자동화 ===")
            print("\n사용 가능한 계정:")
            for i, account in enumerate(ACCOUNTS, 1):
                print(f"{i}. {account}")
            
            while True:
                try:
                    choice = safe_input("\n계정을 선택하세요 (번호 입력): ")
                    choice = int(choice) - 1
                    if 0 <= choice < len(ACCOUNTS):
                        selected_account = ACCOUNTS[choice]
                        break
                    else:
                        print("올바른 번호를 입력해주세요.")
                except ValueError:
                    print("숫자를 입력해주세요.")
            
            print(f"\n[{selected_account}] 계정으로 자동화 시작")
            
            # 전달 자동 설정
            today = datetime.now()
            last_month = today - relativedelta(months=1)
            start_date = last_month.replace(day=1)  # 전달 1일
            end_date = (last_month.replace(day=1) + relativedelta(months=1)) - timedelta(days=1)  # 전달 말일
            
            print(f"\n자동 설정된 날짜 범위: {start_date.strftime('%Y.%m.%d')} ~ {end_date.strftime('%Y.%m.%d')}")
            print("(현재 달의 전달 1일부터 말일까지)")
            
            # 모든 입력이 끝난 후에만 드라이버 실행
            self.setup_driver()
            
            if not self.load_cookie(selected_account):
                print("저장된 쿠키가 없거나 만료되었습니다. 새로 로그인해주세요.")
                self.save_login_cookie(selected_account)
                if not self.load_cookie(selected_account):
                    print("로그인에 실패했습니다.")
                    return
            
            for page_url, page_name in TARGET_PAGES:
                try:
                    self.process_account_page(selected_account, page_url, page_name, start_date, end_date)
                except Exception as e:
                    print(f"{page_name} 페이지 처리 중 오류: {e}")
                    continue
            
            print(f"\n=== {selected_account} 처리 완료 ===")
            
        except Exception as e:
            print(f"오류 발생: {e}")
        finally:
            if self.driver:
                self.driver.quit()

if __name__ == "__main__":
    automation = NaverWorksAutomation()
    automation.main() 