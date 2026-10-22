"""scripts/render_report.py 합성(synthetic) 테스트.

보고서 원고(docs/report/report_v1.md)의 숫자는 `{{key}}` / `{{key|fmt}}` 토큰으로만
쓰고, 렌더러가 outputs/numbers.csv 값으로 치환한다. 여기서는 실데이터 없이
작은 numbers 사전과 임시 파일만으로 형식·실패 조건을 검증한다.
"""
import csv
import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "render_report.py"
_spec = importlib.util.spec_from_file_location("render_report", _SCRIPT_PATH)
render_report = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = render_report
_spec.loader.exec_module(render_report)

render = render_report.render
RenderError = render_report.RenderError
main = render_report.main


NUMBERS = {
    "share": "0.2278",
    "share_half": "0.4545",
    "pop": "426267.8",
    "small": "1291.77",
    "ratio": "0.8785",
    "raw_km": "264.7",
    "zero": "0.0",
}


# --- formats ---------------------------------------------------------------

def test_raw_token_inserts_value_verbatim():
    assert render("연장 {{raw_km}}km", NUMBERS) == "연장 264.7km"


def test_pct1_multiplies_by_100_one_decimal_percent_sign():
    assert render("{{share|pct1}}", NUMBERS) == "22.8%"


def test_pct1_rounds_half_up_from_decimal_string_not_binary_float():
    # float(0.4545)*100 = 45.449999... -> "%.1f"는 45.4가 된다. 문자열 기준 반올림이어야 45.5.
    assert render("{{share_half|pct1}}", NUMBERS) == "45.5%"


def test_int_rounds_and_adds_thousands_separator():
    assert render("{{pop|int}}명", NUMBERS) == "426,268명"
    assert render("{{small|int}}", NUMBERS) == "1,292"


def test_f2_two_decimals():
    assert render("{{ratio|f2}}", NUMBERS) == "0.88"
    assert render("{{zero|f2}}", NUMBERS) == "0.00"


def test_multiple_tokens_on_one_line_and_whitespace_inside_braces():
    text = "{{ share|pct1 }} / {{pop | int}} / {{raw_km}}"
    assert render(text, NUMBERS) == "22.8% / 426,268 / 264.7"


# --- failures ---------------------------------------------------------------

def test_missing_key_fails_and_lists_every_missing_key():
    with pytest.raises(RenderError) as exc:
        render("{{nope}} 그리고 {{also_nope|pct1}} 그리고 {{share}}", NUMBERS)
    msg = str(exc.value)
    assert "nope" in msg and "also_nope" in msg


def test_unknown_format_fails():
    with pytest.raises(RenderError) as exc:
        render("{{share|pct2}}", NUMBERS)
    assert "pct2" in str(exc.value)


def test_non_numeric_value_with_numeric_format_fails():
    with pytest.raises(RenderError):
        render("{{label|int}}", {"label": "향남읍"})


def test_malformed_token_fails_instead_of_leaking_braces():
    with pytest.raises(RenderError):
        render("{{bad key}}", NUMBERS)


# --- no tokens --------------------------------------------------------------

def test_text_without_tokens_is_unchanged():
    text = "# 제목\n\n2.5km = 15km/h × 10분. 표본은 2026-09-15 기준.\n| a | b |\n"
    assert render(text, NUMBERS) == text


# --- CLI ----------------------------------------------------------------------

def _write_numbers(path: Path, rows: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["key", "value", "note"])
        w.writeheader()
        for k, v in rows.items():
            w.writerow({"key": k, "value": v, "note": ""})


def test_cli_writes_rendered_file_with_default_paths(tmp_path):
    _write_numbers(tmp_path / "outputs" / "numbers.csv", NUMBERS)
    src = tmp_path / "docs" / "report" / "report_v1.md"
    src.parent.mkdir(parents=True)
    src.write_text("합의 {{share|pct1}}\n", encoding="utf-8")

    code = main(["--repo-root", str(tmp_path)])

    assert code == 0
    out = tmp_path / "outputs" / "report_v1_rendered.md"
    assert out.read_text(encoding="utf-8") == "합의 22.8%\n"


def test_cli_returns_nonzero_and_writes_nothing_on_missing_key(tmp_path, capsys):
    _write_numbers(tmp_path / "outputs" / "numbers.csv", NUMBERS)
    src = tmp_path / "in.md"
    src.write_text("{{missing_one}} {{share|bogus}}\n", encoding="utf-8")
    out = tmp_path / "out.md"

    code = main(["--repo-root", str(tmp_path), "--in", str(src), "--out", str(out)])

    assert code != 0
    assert not out.exists()
    err = capsys.readouterr().err
    assert "missing_one" in err and "bogus" in err
