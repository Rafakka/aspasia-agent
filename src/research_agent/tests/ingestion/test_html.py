

from research_agent.ingestion.workers.html import extract_html


def test_extract_html_content():
    html = b"""
    <!DOCTYPE html>
    <html>
        <head>
            <title>Teste Aspasia</title>
        </head>
        <body>
            <article>
                <h1>Investigacao sobre tecnologia</h1>
                <p>
                    Este e um texto de exemplo para testar
                    a extracao de conteudo da Aspasia.
                </p>
            </article>
        </body>
    </html>
    """

    result = extract_html(
        content=html,
        url="https://example.com/article",
    )

    assert result is not None
    assert "Investigacao sobre tecnologia" in result
    assert "texto de exemplo" in result


def test_extract_html_empty_content():
    try:
        extract_html(b"")
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_extract_html_without_readable_content():
    html = b"""
    <!DOCTYPE html>
    <html>
        <head><title>Empty page</title></head>
        <body></body>
    </html>
    """

    result = extract_html(html)

    assert result is None

