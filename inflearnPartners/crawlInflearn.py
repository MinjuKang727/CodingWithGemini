import io
import os
import time
from PIL import Image, ImageDraw
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# 분리된 키워드 분석 모듈 임포트
from keyword_analyzer import KeywordManager

def cm_to_px(cm, dpi=96):
    """cm 단위를 픽셀로 변환"""
    return int(cm * (dpi / 2.54))

def get_full_scroll_stitched_image(driver, save_path):
    """
    1. 하단 불필요 섹션 제거
    2. 화면 높이만큼 스크롤하며 조각 캡처
    3. 22.7cm 규격 병합 + 14.5cm 화이트 아웃 + 사이드바 정밀 합성
    """
    # 규격 설정 (DPI에 따른 변환)
    TOTAL_WIDTH_PX = cm_to_px(22.7)
    WHITE_START_PX = cm_to_px(14.5)
    GAP_PX = cm_to_px(0.5)

    # 1. 스타일 강제 적용 (불필요 요소 제거 및 레이아웃 고정)
    driver.execute_script("""
        const unwanted = document.querySelector('section.css-1h0915r');
        if(unwanted) unwanted.style.display = 'none';
        
        const hideList = ['nav.course-nav', '.mantine-Header-root', 'header'];
        hideList.forEach(s => { 
            const el = document.querySelector(s); 
            if(el) el.style.display = 'none !important'; 
        });
        document.body.style.overflow = 'visible';
    """)
    time.sleep(1)

    # 2. 사이드바(가격 영역) 및 헤더 높이 미리 측정
    try:
        side_el = driver.find_element(By.CLASS_NAME, "css-ks8w16")
        side_img_bytes = side_el.screenshot_as_png
        side_img = Image.open(io.BytesIO(side_img_bytes))
        
        header_el = driver.find_element(By.CSS_SELECTOR, "section.css-1pno9se")
        header_height = header_el.size['height']
    except:
        side_img = None
        header_height = 0

    # 3. 스크롤 캡처 진행
    view_height = driver.execute_script("return window.innerHeight")
    # 하단 섹션을 숨겼으므로 현재 상태의 실제 높이 다시 계산
    total_height = driver.execute_script("return document.body.scrollHeight")
    
    # 22.7cm 규격의 베이스 캔버스 생성 (세로는 스크롤 전체 높이)
    stitched_image = Image.new('RGB', (TOTAL_WIDTH_PX, total_height), (255, 255, 255))
    
    current_pos = 0
    while current_pos < total_height:
        driver.execute_script(f"window.scrollTo(0, {current_pos});")
        time.sleep(0.7) # 렌더링 대기
        
        # 현재 화면 캡처
        screenshot_bytes = driver.get_screenshot_as_png()
        part_img = Image.open(io.BytesIO(screenshot_bytes))
        
        # 마지막 조각 처리: 남은 높이만큼 자르기
        if current_pos + view_height > total_height:
            crop_h = total_height - current_pos
            part_img = part_img.crop((0, 0, part_img.width, crop_h))
            stitched_image.paste(part_img, (0, current_pos))
            break
        
        stitched_image.paste(part_img, (0, current_pos))
        current_pos += view_height

    # 4. 정밀 합성 (덮어쓰기 로직)
    draw = ImageDraw.Draw(stitched_image)
    
    # 14.5cm(WHITE_START_PX) 지점부터 우측 끝까지 하얀색 배경으로 덮어쓰기
    # (이미지 전체 높이에 대해 적용)
    draw.rectangle([WHITE_START_PX, 0, TOTAL_WIDTH_PX, total_height], fill=(255, 255, 255))

    # 사이드바를 지정된 위치에 덮어쓰기 (헤더 하단 + 0.5cm)
    if side_img:
        stitched_image.paste(side_img, (WHITE_START_PX, header_height + GAP_PX))

    stitched_image.save(save_path)
    print(f"이미지 캡처 및 정밀 합성 완료: {save_path}")

def crawl_inflearn_partners():
    km = KeywordManager()
    options = Options()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        driver.get("https://www.inflearn.com/")
        print("20초 안에 로그인을 완료하세요...")
        time.sleep(20) 

        main_window = driver.current_window_handle
        driver.get("https://www.inflearn.com/my/partners-links")
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CLASS_NAME, "ag-row")))
        time.sleep(3)

        links = driver.find_elements(By.CSS_SELECTOR, ".ag-row-odd a, .ag-row-even a")
        hrefs = [link.get_attribute('href') for link in links[:2]]
        
        if not os.path.exists("captures"): os.makedirs("captures")

        for idx, url in enumerate(hrefs):
            print(f"\n--- [{idx+1}/{len(hrefs)}] 작업 시작: {url} ---")
            driver.execute_script(f"window.open('{url}', '_blank');")
            time.sleep(3)
            driver.switch_to.window(driver.window_handles[-1])

            try:
                # 1. 텍스트 추출 및 AI 키워드 분석
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "main")))
                course_data = driver.execute_script("""
                    return {
                        title: document.querySelector('h1')?.innerText || '제목없음',
                        mainText: document.querySelector('main')?.innerText || document.body.innerText
                    };
                """)
                
                # 동적 키워드 설명 생성 (분리된 파일 로직)
                concept_explanation = km.get_unique_keywords_and_explain(course_data['title'], course_data['mainText'])

                # 2. 스크롤 캡처 및 정밀 합성 이미지 실행
                img_file = f"captures/course_{idx+1}_final.png"
                get_full_scroll_stitched_image(driver, img_file)

                # 3. 텍스트 정보 저장 (AI 설명 포함)
                with open(f"captures/course_{idx+1}_info.txt", "w", encoding="utf-8") as f:
                    f.write(f"URL: {url}\nTITLE: {course_data['title']}\n\n")
                    f.write(concept_explanation + "\n")
                    f.write("-" * 50 + "\n[본문 내용]\n")
                    f.write(course_data['mainText'])

                print(f"처리 완료: {course_data['title']}")

            except Exception as e:
                print(f"에러 발생: {e}")
            
            driver.close()
            driver.switch_to.window(main_window)
            time.sleep(1)

    finally:
        driver.quit()
        print("\n모든 작업이 완료되었습니다.")

if __name__ == "__main__":
    crawl_inflearn_partners()