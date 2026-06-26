"""shared/html_common.py render_page 검증 (구 _smoke_test 이관, tempfile 쓰기 제거)."""

from topic_pipeline.shared import html_common


def test_render_page_structure():
    body = '<h1>Phase 2e 샘플</h1>\n<div class="summary">한글 UTF-8 렌더 확인</div>'
    html = html_common.render_page("샘플 제목", body)

    assert html.startswith("<!DOCTYPE html>")
    assert "<style>" in html and "</style>" in html
    assert "'Apple SD Gothic Neo'" in html
    assert "한글 UTF-8 렌더 확인" in html
    assert "샘플 제목" in html
    assert "</body>" in html and "</html>" in html


def test_render_page_head_extra():
    html = html_common.render_page("t", "<p>x</p>", head_extra='<meta name="probe">')
    assert '<meta name="probe">' in html
