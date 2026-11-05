from policylab.chunking import chunk_document, paragraphs_from_text

HTML = """<html><body><pre>
[Federal Register Volume 89, Number 1 (Monday, January 1, 2024)]
[Rules and Regulations]

-----------------------------------------------------------------------

ACTION: Final rule.

SUMMARY: This rule sets ``healthy'' limits for school
breakfast cereals so that they contain no more than 6 grams of
added sugars per dry

[[Page 101]]

ounce. Schools must comply by July 1, 2025.

I. Background

The agency received many comments.
</pre></body></html>"""


def test_page_break_mid_sentence_is_rejoined():
    paras = paragraphs_from_text(HTML.split("<pre>")[1].split("</pre>")[0])
    texts = [p.text for p in paras]
    joined = [t for t in texts if "per dry ounce" in t]
    assert joined, texts
    assert "[[Page" not in joined[0]


def test_tex_quotes_normalised_and_heading_detected():
    paras, chunks = chunk_document("2024-00001", HTML)
    assert any("“healthy”" in p.text for p in paras)
    assert any(p.is_heading and p.text == "I. Background" for p in paras)
    assert chunks[-1].section == "I. Background"


def test_chunk_ids_are_deterministic():
    _, a = chunk_document("2024-00001", HTML)
    _, b = chunk_document("2024-00001", HTML)
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]
    assert all(c.chunk_id.startswith("2024-00001:p") for c in a)


def test_page_numbers_tracked():
    paras, _ = chunk_document("2024-00001", HTML)
    background = next(p for p in paras if p.text == "I. Background")
    assert background.page == 101
