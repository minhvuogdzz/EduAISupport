"""REL-1: ``make tunnel`` shows the public address and the few warnings. Offline: a stub stands in for
cloudflared; no tunnel is opened and nothing reaches Cloudflare."""

import stat

import pytest
from cavat import tunnel

LOG = """\
2026-10-26T10:00:00Z INF Thank you for trying Cloudflare Tunnel. Doing so, without a Cloudflare account...
2026-10-26T10:00:02Z INF Requesting new quick Tunnel on trycloudflare.com...
2026-10-26T10:00:03Z INF +------------------------------------------+
2026-10-26T10:00:03Z INF |  Your quick Tunnel has been created! Visit it at:  |
2026-10-26T10:00:03Z INF |  https://cats-and-dogs-play-together.trycloudflare.com  |
2026-10-26T10:00:03Z INF +------------------------------------------+
"""


def stub(tmp_path, body: str, name="cloudflared"):
    path = tmp_path / name
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def run(argv, **kw):
    return tunnel.main(argv, **{"cavat_answers": lambda port: True, **kw})


@pytest.mark.parametrize(
    ("line", "url"),
    [
        (LOG.splitlines()[4], "https://cats-and-dogs-play-together.trycloudflare.com"),
        ("visit https://a1.trycloudflare.com/ now", "https://a1.trycloudflare.com"),
        (LOG.splitlines()[1], None),  # "trycloudflare.com..." without a host is not an address
        ("https://example.com/trycloudflare.com", None),
        ("https://evil.example/?u=https://x.trycloudflare.com.evil.example", "https://x.trycloudflare.com"),
    ],
)
def test_the_address_is_picked_out_of_the_log(line, url):
    assert tunnel.find_public_url(line) == url


def test_the_banner_has_the_address_and_what_to_remember():
    text = tunnel.banner("https://a.trycloudflare.com", caffeinated=True)
    assert "https://a.trycloudflare.com" in text
    assert "PIN" in text
    assert "đổi PIN" in text
    assert "tài khoản học sinh" in text
    assert "caffeinate -i đang giữ máy" in text
    assert "tự giữ máy không ngủ" in tunnel.banner("https://a.trycloudflare.com", caffeinated=False)


def test_the_run_prints_the_log_then_the_address_and_ends_with_the_tunnel(tmp_path, capsys):
    fake = stub(tmp_path, f"cat <<'EOF'\n{LOG}EOF\ncat >/dev/null <<'EOF'\nEOF\n")
    code = run(["--port", "18080", "--cloudflared", fake], which=lambda name: fake if name == fake else None)
    out = capsys.readouterr().out
    assert code == 0
    assert "Địa chỉ công khai:  https://cats-and-dogs-play-together.trycloudflare.com" in out
    assert out.count("Địa chỉ công khai:") == 1  # the address in the log's box shows once
    assert "Your quick Tunnel has been created" in out  # the log is still shown
    assert "tự giữ máy không ngủ" in out  # no caffeinate in this run
    assert "Đường hầm đã tắt" in out


def test_cloudflared_is_started_for_the_port_given(tmp_path, capsys):
    record = tmp_path / "args"
    fake = stub(tmp_path, f'echo "$@" > {record}')
    run(["--port", "18080", "--cloudflared", fake], which=lambda name: fake if name == fake else None)
    assert record.read_text().split() == ["tunnel", "--url", "http://localhost:18080"]


def test_caffeinate_rides_with_the_tunnel_when_the_machine_has_it(tmp_path, capsys):
    record = tmp_path / "args"
    # Keep the fake tunnel alive until its companion has executed. Otherwise a fast fake can exit
    # before the OS schedules caffeinate, and normal cleanup kills it before it writes the arguments.
    fake = stub(
        tmp_path,
        f'i=0; while [ ! -f "{record}" ] && [ "$i" -lt 100 ]; do '
        f"i=$((i + 1)); sleep 0.01; done\ncat <<'EOF'\n{LOG}EOF",
    )
    awake = stub(tmp_path, f'echo "$@" > {record}', name="caffeinate")
    run(
        ["--port", "18080", "--cloudflared", fake],
        which=lambda name: {fake: fake, "caffeinate": awake}.get(name),
    )
    flags = record.read_text().split()
    assert flags[:2] == ["-i", "-w"]  # -w: ends when cloudflared ends
    assert flags[2].isdigit()
    assert "caffeinate -i đang giữ máy" in capsys.readouterr().out


def test_without_cloudflared_it_says_how_to_install_it(capsys):
    assert run(["--cloudflared", "no-such-tool"], which=lambda name: None) == 1
    assert "brew install cloudflared" in capsys.readouterr().out


def test_without_a_server_at_the_port_it_does_not_open_a_tunnel_to_nothing(tmp_path, capsys):
    fake = stub(tmp_path, "touch " + str(tmp_path / "started"))
    code = run(
        ["--port", "18080", "--cloudflared", fake],
        cavat_answers=lambda port: False,
        which=lambda name: fake,
    )
    assert code == 1
    assert "make run" in capsys.readouterr().out
    assert not (tmp_path / "started").exists()
