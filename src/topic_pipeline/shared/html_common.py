"""HTML 리포트 공통 CSS + 페이지 wrap.

PLAN-v2 §8 Phase 2e. 원본 CSS: 06_Clustered_Topic_Assay_v3/clustered_topic_report.py:483-512.
섹션 렌더 헬퍼는 소비자 패턴 확인 후 추출.
"""

from __future__ import annotations

CSS = """  body { font-family: 'Apple SD Gothic Neo', 'Nanum Gothic', sans-serif;
         max-width: 1100px; margin: 40px auto; padding: 0 20px;
         color: #2c3e50; line-height: 1.6; }
  h1 { border-bottom: 2px solid #2c3e50; padding-bottom: 8px; }
  h2 { color: #1a5276; margin-top: 40px; }
  h3 { color: #2c3e50; margin-top: 24px; }
  .summary { background: #f8f9fa; padding: 12px 20px; border-radius: 6px;
              margin-bottom: 30px; }
  table { border-collapse: collapse; width: 100%; margin: 16px 0; }
  th { background: #1a5276; color: white; padding: 10px 12px; text-align: left; }
  td { padding: 8px 12px; border-bottom: 1px solid #ddd; }
  tr:hover td { background: #f0f6fb; }
  .desc-cell { font-size: 0.88em; color: #555; padding-left: 24px;
                border-bottom: 2px solid #eee; }
  .chart-section { margin: 30px 0; }
  .comment-box { background: #fffbe6; border: 1px dashed #d4a017;
                  padding: 20px; border-radius: 6px; min-height: 80px;
                  margin-top: 20px; }
  .comment-box p { color: #888; font-style: italic; }
  .draft-badge { display: inline-block; background: #e74c3c; color: white;
                  padding: 2px 8px; border-radius: 4px; font-size: 0.8em;
                  margin-left: 8px; }
  .note-box { background: #eaf2f8; padding: 12px 20px; border-radius: 6px;
               border-left: 4px solid #2e86c1; margin: 16px 0; }
  details summary { padding: 4px 0; }
  img.chart-img { max-width: 100%; height: auto; border: 1px solid #eee;
                   border-radius: 4px; margin: 12px 0; }
  .interact-hint { color: #666; font-size: 0.92em; margin-bottom: 8px; }
"""


def render_page(title: str, body_html: str, head_extra: str = "") -> str:
    """공통 CSS 적용된 HTML 전체 문서 반환. head_extra 는 추가 head 삽입 슬롯."""
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>{title}</title>
{head_extra}
<style>
{CSS}</style>
</head>
<body>
{body_html}
</body>
</html>
"""


def _smoke_test() -> None:
    """샘플 섹션 렌더 검증 (PLAN-v2 §8 Phase 2e)."""
    import tempfile
    from pathlib import Path

    body = (
        "<h1>Phase 2e 샘플</h1>\n"
        '<div class="summary"><ul>'
        "<li>한글 UTF-8 렌더 확인</li>"
        "<li>CSS 클래스 적용 확인</li>"
        "</ul></div>\n"
        '<div class="note-box">note-box 스타일 확인용 메모.</div>'
    )
    html = render_page("Phase 2e 샘플", body)

    assert html.startswith("<!DOCTYPE html>"), "DOCTYPE 누락"
    assert "<style>" in html and "</style>" in html
    assert "'Apple SD Gothic Neo'" in html, "font-family 누락"
    assert "한글 UTF-8 렌더 확인" in html
    assert "</body>" in html and "</html>" in html

    out = Path(tempfile.gettempdir()) / "phase2e_sample.html"
    out.write_text(html, encoding="utf-8")
    print(f"[OK] render_page 통과: {len(html)} chars")
    print(f"     브라우저 확인용: open {out}")


if __name__ == "__main__":
    _smoke_test()
