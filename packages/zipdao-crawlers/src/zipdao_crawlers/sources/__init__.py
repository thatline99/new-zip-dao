"""사이트별 크롤러 구현.

새 사이트를 추가하려면:
  1. 이 디렉터리에 `<source_key>.py` 를 만들고 `BaseCrawler` 를 상속한다
     (구현 골격은 `_template.py` 참고).
  2. `registry.py` 의 해당 `SourceInfo(crawler=...)` 에 클래스를 연결한다.
"""
