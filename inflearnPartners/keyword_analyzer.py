import json
import os

class KeywordManager:
    def __init__(self, filename="used_keywords.json"):
        self.filename = filename
        self.used_data = self._load()

    def _load(self):
        """저장된 키워드 기록을 불러옵니다."""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_to_file(self):
        """업데이트된 키워드 기록을 저장합니다."""
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self.used_data, f, ensure_ascii=False, indent=4)

    def get_unique_keywords_and_explain(self, course_title, main_text):
        """
        AI가 추출한 키워드 중 중복되지 않은 것을 선별하고 설명을 생성합니다.
        (현재는 로직 예시이며, 실제 AI API 연결 시 이 부분을 수정합니다.)
        """
        
        # [중요] 실제로는 여기서 AI API를 호출하여 본문(main_text)에서 키워드를 뽑습니다.
        # 지금은 강의 내용에 포함될 법한 임시 리스트를 사용합니다.
        all_extracted = ["Spring Boot", "Docker", "JPA", "AWS EC2", "MySQL", "Redis", "CI/CD", "React", "Python"]
        
        # 이 강의 본문에서 실제 발견된 키워드만 필터링 (간단한 예시용)
        found_in_text = [k for k in all_extracted if k.lower() in main_text.lower() or k.lower() in course_title.lower()]
        
        # 발견된 게 너무 적으면 기본 키워드 사용
        if len(found_in_text) < 3:
            found_in_text = all_extracted[:5]

        if course_title not in self.used_data:
            self.used_data[course_title] = []

        # 중복 제외 필터링 (이미 이 강의에서 설명했던 키워드 제외)
        used_list = self.used_data[course_title]
        new_keywords = [k for k in found_in_text if k not in used_list]

        # 만약 해당 강의의 모든 키워드를 다 설명했다면 기록 초기화 후 다시 시작
        if not new_keywords:
            new_keywords = found_in_text
            self.used_data[course_title] = []

        # 이번 포스팅에 사용할 키워드 3개 선택
        selected = new_keywords[:3]
        
        # 키워드별 개념 설명 생성 (이 부분도 나중에 AI API가 작성하도록 변경 가능)
        explanation = f"### 📚 [{course_title}] 관련 핵심 개념 정리\n"
        for k in selected:
            # 예시 설명 (실제로는 AI가 작성한 문구가 들어가는 곳)
            desc = f"{k} 기술의 핵심 특징과 이번 강의에서의 활용 방안을 정리했습니다." 
            explanation += f"- **{k}**: {desc}\n"
        
        # 사용 기록 업데이트 및 파일 저장
        self.used_data[course_title].extend(selected)
        self.save_to_file()
        
        return explanation