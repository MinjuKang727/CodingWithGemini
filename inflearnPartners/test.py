import io
import time
import os
import re
from PIL import Image, ImageDraw
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def clean_filename(text):
    return re.sub(r'[\\/*?:"<>|]', "", text).strip()

def capture_inflearn_detail():
    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    if not os.path.exists("captures"): os.makedirs("captures")

    try:
        # 1. 요소 대기 및 정보 취득
        info_section = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "css-1pno9se")))
        course_title = driver.find_element(By.TAG_NAME, "h1").text
        
        # 2. 화면 정리 (헤더 숨기기 및 채널톡 제거)
        driver.execute_script("""
            const junk = ['header', '.mantine-Header-root', '#ch-plugin', '.course-nav'];
            junk.forEach(s => document.querySelectorAll(s).forEach(el => el.style.display = 'none'));
        """)
        time.sleep(1)

        # 3. 정확한 좌표 계산 (JS 실행)
        rects = driver.execute_script("""
            const info = document.querySelector('.css-1pno9se');
            const limit = document.querySelector('section.css-1h0915r') || document.body;
            const side = document.querySelector('.css-ks8w16');
            
            return {
                start: info.getBoundingClientRect().top + window.scrollY,
                end: limit.getBoundingClientRect().top + window.scrollY,
                viewportH: window.innerHeight,
                docW: document.documentElement.clientWidth,
                sideLeft: side ? side.getBoundingClientRect().left : 0,
                sideTop: side ? side.getBoundingClientRect().top + window.scrollY : 0
            };
        """)

        total_height = int(rects['end'] - rects['start'])
        print(f"📊 캡처 범위: {rects['start']}px ~ {rects['end']}px (총 {total_height}px)")

        if total_height <= 0:
            print("❌ 캡처할 영역이 없습니다. 섹션 클래스명을 확인하세요.")
            return

        # 4. 캔버스 생성
        full_img = Image.new('RGB', (rects['docW'], total_height), (255, 255, 255))
        
        # 5. 강제 스크롤 및 캡처 루프
        curr_y = rects['start']
        while curr_y < rects['end']:
            # 스크롤 명령 (scrollTo와 scrollTop 강제 주입 병행)
            driver.execute_script(f"""
                window.scrollTo(0, {curr_y});
                document.documentElement.scrollTop = {curr_y};
            """)
            time.sleep(0.8) # 렌더링 대기
            
            # 실제 스크롤된 위치 확인 (검증용)
            current_actual_y = driver.execute_script("return window.scrollY || document.documentElement.scrollTop")
            
            # 캡처 및 붙여넣기
            screenshot = Image.open(io.BytesIO(driver.get_screenshot_as_png()))
            paste_y = int(curr_y - rects['start'])
            
            # 마지막 조각 크롭 처리
            if paste_y + rects['viewportH'] > total_height:
                crop_h = total_height - paste_y
                screenshot = screenshot.crop((0, 0, screenshot.width, crop_h))
            
            full_img.paste(screenshot, (0, paste_y))
            print(f"📸 캡처 진행 중: {paste_y}/{total_height} px")
            
            curr_y += rects['viewportH']

        # 6. 사이드바 하단 마스킹 및 저장
        draw = ImageDraw.Draw(full_img)
        mask_y = int(rects['sideTop'] - rects['start'] + 450)
        if mask_y < total_height:
            draw.rectangle([int(rects['sideLeft'] - 20), mask_y, rects['docW'], total_height], fill=(255, 255, 255))

        # 좌우 크롭 후 저장
        final_img = full_img.crop((100, 0, rects['docW'] - 100, total_height))
        save_path = f"captures/{clean_filename(course_title)}.png"
        final_img.save(save_path)
        print(f"✅ 최종 이미지 저장 성공: {save_path}")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    capture_inflearn_detail()