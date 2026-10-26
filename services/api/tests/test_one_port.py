"""REL-1 (ADR-034): the API serves the web build at one port, with a JSON 404 for the API's own paths, long
caching for hashed files, light security headers, gzip and no docs. Offline: a fake dist folder."""

import pytest
from cavat.main import create_app
from fastapi.testclient import TestClient

INDEX = '<!doctype html><html><head><title>CAVAT</title></head><body><div id="root"></div></body></html>'
BUNDLE = "console.log('cavat');" * 200  # compressible, over the gzip minimum


@pytest.fixture
def dist(tmp_path):
    folder = tmp_path / "dist"
    (folder / "assets").mkdir(parents=True)
    (folder / "index.html").write_text(INDEX, encoding="utf-8")
    (folder / "assets" / "index-Ab12Cd34.js").write_text(BUNDLE, encoding="utf-8")
    (folder / "favicon.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    (folder / ".cavat-build").write_text("{}", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("not for the browser", encoding="utf-8")
    return folder


@pytest.fixture
def client(dist):
    return TestClient(create_app(web_dist=dist, api_docs=False))


def test_the_root_is_the_web_app(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert '<div id="root">' in r.text


@pytest.mark.parametrize(
    "path", ["/student", "/student/sessions/abc", "/teacher/documents/xyz", "/parent/ABCD", "/no/such/page"]
)
def test_the_paths_of_the_web_app_get_index_html(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert '<div id="root">' in r.text


def test_the_health_check_and_the_api_stay_the_api(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/v1/auth/config").status_code == 200


@pytest.mark.parametrize("path", ["/v1/nothing", "/v1/sessions/abc/nothing", "/v1", "/health/nothing"])
def test_a_missing_api_path_is_a_json_404_not_the_web_app(client, path):
    r = client.get(path)
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["error"]["code"] == "NOT_FOUND"
    assert "root" not in r.text


def test_a_post_to_a_missing_path_is_a_json_404(client):
    r = client.post("/student/anything", json={})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_a_wrong_method_on_an_api_path_is_still_a_405(client):
    r = client.get("/v1/sessions/abc/responses")  # POST only
    assert r.status_code == 405


def test_hashed_files_are_cached_for_a_year_and_the_page_is_revalidated(client):
    asset = client.get("/assets/index-Ab12Cd34.js")
    assert asset.status_code == 200
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    for path in ("/", "/student/sessions/abc", "/favicon.svg"):
        assert client.get(path).headers["cache-control"] == "no-cache"


def test_an_unchanged_page_answers_304(client):
    first = client.get("/")
    r = client.get("/", headers={"If-None-Match": first.headers["etag"]})
    assert r.status_code == 304
    assert r.headers["cache-control"] == "no-cache"


def test_a_missing_file_is_a_404_not_the_web_app(client):
    for path in ("/assets/gone.js", "/robots.txt", "/assets/"):
        r = client.get(path)
        assert r.status_code == 404, path
        assert "root" not in r.text


@pytest.mark.parametrize(
    "path", ["/.cavat-build", "/assets/../.cavat-build", "/%2e%2e/secret.txt", "/..%2fsecret.txt"]
)
def test_nothing_outside_the_build_and_no_dotfiles(client, path):
    r = client.get(path)
    assert "not for the browser" not in r.text
    assert r.text != "{}"


def test_security_headers_on_the_page_the_api_and_the_404(client):
    for path in ("/", "/assets/index-Ab12Cd34.js", "/health", "/v1/nothing"):
        h = client.get(path).headers
        assert h["x-content-type-options"] == "nosniff", path
        assert h["referrer-policy"] == "same-origin", path
        assert h["x-frame-options"] == "DENY", path
        assert "frame-ancestors 'none'" in h["content-security-policy"], path


def test_text_is_gzipped_when_the_browser_accepts_it(client):
    zipped = client.get("/assets/index-Ab12Cd34.js", headers={"Accept-Encoding": "gzip"})
    assert zipped.headers["content-encoding"] == "gzip"
    assert "accept-encoding" in zipped.headers["vary"].lower()
    assert int(zipped.headers["content-length"]) < len(BUNDLE)
    assert zipped.text == BUNDLE  # the client unpacks it
    plain = client.get("/assets/index-Ab12Cd34.js", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in plain.headers
    assert plain.text == BUNDLE


def test_no_cors_so_another_site_cannot_read_the_answers(client):
    r = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers
    pre = client.options(
        "/v1/auth/login",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in pre.headers


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"])
def test_the_docs_are_off_by_default(client, path):
    r = client.get(path)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_the_docs_come_back_with_api_docs(dist):
    on = TestClient(create_app(web_dist=dist, api_docs=True))
    assert on.get("/openapi.json").status_code == 200
    assert "swagger" in on.get("/docs").text.lower()


def test_without_a_build_it_is_the_api_alone(tmp_path):
    api = TestClient(create_app(web_dist=tmp_path / "missing"))
    assert api.get("/health").json()["status"] == "ok"
    for path in ("/", "/student", "/assets/x.js"):
        r = api.get(path)
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "NOT_FOUND"


def test_the_settings_say_where_the_build_is(monkeypatch, tmp_path):
    from cavat.config import Settings

    monkeypatch.setenv("WEB_DIST", str(tmp_path))
    monkeypatch.setenv("API_DOCS", "1")
    settings = Settings(_env_file=None)
    assert settings.web_dist == tmp_path
    assert settings.api_docs is True
    monkeypatch.delenv("WEB_DIST")
    monkeypatch.delenv("API_DOCS")
    default = Settings(_env_file=None)
    assert default.web_dist.parts[-3:] == ("apps", "web", "dist")
    assert default.api_docs is False
