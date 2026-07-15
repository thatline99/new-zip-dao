# 데이터 디렉터리 레이아웃

수집 원본은 모두 `data/` 아래에 저장되며 **git 추적 제외**(`.gitignore`)다.
(로컬 디스크 → 추후 OCI 서버, 백업은 Google Drive로 rclone sync.)

```
data/
├── raw/                                  # 원본 산출물(소스 → 연도 → 공고)
│   └── <source>/                         # 예: lh_apply, sh_ish, applyhome, ...
│       └── <YYYY>/                       # 공고 게시 연도 (없으면 unknown)
│           └── <notice_id>/              # 공고 1건
│               ├── manifest.json         # 메타 + 첨부목록 + sha256 + 수집시각
│               ├── detail.html           # 상세 페이지 스냅샷(있을 때)
│               ├── attachments/          # PDF·HWP·HWPX·ZIP·문서
│               │   ├── 공고문.pdf
│               │   └── 신청서.hwp
│               └── images/               # 공고 내 이미지(평면도 등)
│                   ├── 평면도.jpg
│                   └── ...
└── last_crawl                            # (집서버) 크론이 기록하는 마지막 수집 시각(UTC)
```

정규화 산출물은 별도 디렉터리가 아니라 **각 manifest 의 `raw.normalized` 블록**에 저장된다
(보증금·월세·면적·공급유형·접수기간·당첨자발표일 등 — 서빙 API 가 읽는 필드).
공고문 PDF 파싱 결과(나이 자격·청년 가격)는 `raw.docParse` 로 병합된다.
백필 명령: `zipdao-crawl normalize all` / `zipdao-crawl parse-docs all`.

## 설계 원칙

- **멱등성**: `manifest.json` 이 있으면 수집 완료로 보고 재실행 시 스킵(`--force`로 재수집).
- **무결성**: 모든 첨부는 sha256·바이트수를 manifest에 기록 → 백업 검증·중복 제거 근거.
- **소스/연도 파티션**: 5년치 대량 수집을 사이트·연도로 분할해 부분 동기화/재수집이 쉽다.
- **분리 저장**: 이미지는 `images/`, 그 외 문서는 `attachments/` 로 분리.

## manifest.json 예시

```json
{
  "source": "lh_apply",
  "notice_id": "2024-0001",
  "title": "○○ 행복주택 입주자 모집공고",
  "detail_url": "https://apply.lh.or.kr/...",
  "posted_date": "2024-03-15",
  "category": "행복주택",
  "region": "경기",
  "detail_html_path": "lh_apply/2024/2024-0001/detail.html",
  "attachments": [
    {
      "url": "https://apply.lh.or.kr/.../file.do?id=...",
      "filename": "공고문.pdf",
      "kind": "pdf",
      "local_path": "lh_apply/2024/2024-0001/attachments/공고문.pdf",
      "sha256": "…",
      "bytes": 1234567,
      "downloaded_at": "2026-06-24T05:00:00+00:00"
    }
  ],
  "crawled_at": "2026-06-24T05:00:05+00:00"
}
```
