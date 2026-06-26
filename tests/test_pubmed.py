"""shared/pubmed.py efetch 래퍼 검증 (구 _smoke_test 이관).

라이브 NCBI 호출 → responses mock 으로 대체 (오프라인 가능).
api_key 유무에 따른 rate-limit interval(0.34→0.1) + api_key 파라미터 주입 검증.
"""

import responses

from topic_pipeline.shared import pubmed

CANNED_XML = b"""<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle><MedlineCitation><PMID>12345</PMID></MedlineCitation></PubmedArticle>
  <PubmedArticle><MedlineCitation><PMID>67890</PMID></MedlineCitation></PubmedArticle>
</PubmedArticleSet>"""


def _req_body(call) -> str:
    body = call.request.body
    return body.decode() if isinstance(body, (bytes, bytearray)) else body


@responses.activate
def test_efetch_parses_articles(monkeypatch):
    monkeypatch.setattr(pubmed.time, "sleep", lambda *_: None)
    responses.add(responses.POST, pubmed.EFETCH_URL, body=CANNED_XML, status=200)

    arts = list(pubmed.efetch_articles([12345, 67890]))

    assert len(arts) == 2
    pmids = [a.findtext("MedlineCitation/PMID", "") for a in arts]
    assert all(p.isdigit() for p in pmids)
    assert pmids == ["12345", "67890"]


@responses.activate
def test_api_key_flips_interval_and_param(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(pubmed.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setenv("NCBI_API_KEY", "testkey")
    responses.add(responses.POST, pubmed.EFETCH_URL, body=CANNED_XML, status=200)

    list(pubmed.efetch_articles([1]))

    assert 0.1 in sleeps  # key 있으면 10 req/s
    assert "api_key=testkey" in _req_body(responses.calls[0])


@responses.activate
def test_no_key_uses_slower_interval(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(pubmed.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    responses.add(responses.POST, pubmed.EFETCH_URL, body=CANNED_XML, status=200)

    list(pubmed.efetch_articles([1]))

    assert 0.34 in sleeps  # key 없으면 3 req/s
    assert "api_key" not in _req_body(responses.calls[0])
