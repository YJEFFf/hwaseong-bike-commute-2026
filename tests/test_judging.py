"""scripts/08_judging.py (Task 6: 2인 판독 시트/채점)에 대한 단위 테스트.

파일명이 숫자로 시작해 일반 import 문법을 쓸 수 없으므로 importlib로
scripts/08_judging.py를 직접 불러온다(tests/test_04_access_smoke.py와 동일한
방식). 실제 좌표·브이월드 URL은 절대 다루지 않고 전부 합성(synthetic) 값을
쓴다.
"""
import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "08_judging.py"
_spec = importlib.util.spec_from_file_location("judging_08", _SCRIPT_PATH)
judging_08 = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = judging_08
_spec.loader.exec_module(judging_08)


def _synthetic_private_df(n_segment=110, n_candidate=36, n_island_gap=20, n_placeholder=10):
    """실제 sample_points.csv와 같은 컬럼 구조를 가진 합성 표본(기본 176행)."""
    districts = ["동탄", "만세", "병점", "효행"]
    counts = {
        "segment": n_segment, "candidate": n_candidate,
        "island_gap": n_island_gap, "placeholder": n_placeholder,
    }
    rows = []
    pid = 1
    for sample_type, n_type in counts.items():
        for i in range(n_type):
            rows.append({
                "pid": f"S{pid:03d}",
                "sample_type": sample_type,
                "district": districts[i % len(districts)],
                "stratum": "합의" if sample_type == "segment" else "",
                "x": 200000.0 + pid, "y": 500000.0 + pid,
                "lon": 127.0 + pid * 0.0001, "lat": 37.0 + pid * 0.0001,
                "source_ref": f"src{pid}", "source_origin": "official",
                "target_wkt": f"LINESTRING ({pid} 0, {pid+1} 0)",
                "vworld_url": (
                    f"https://map.vworld.kr/map/maps.do?lat=37.{pid:06d}"
                    f"&lon=127.{pid:06d}&level=18"
                ),
            })
            pid += 1
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 템플릿(validation/judging_sheet_template.csv에 커밋되는 형태)
# ---------------------------------------------------------------------------

def test_template_has_176_rows_from_synthetic_176_row_private_file():
    private_df = _synthetic_private_df()
    assert len(private_df) == 176
    template = judging_08.build_template(private_df)
    assert len(template) == 176


def test_template_columns_have_no_coordinates_or_source_hints():
    private_df = _synthetic_private_df(n_segment=5, n_candidate=5, n_island_gap=5, n_placeholder=5)
    template = judging_08.build_template(private_df)
    assert list(template.columns) == [
        "pid", "sample_type", "district", "judge_id", "label",
        "confidence", "imagery_date", "note",
    ]
    for forbidden in ("x", "y", "lon", "lat", "vworld_url", "stratum", "source_ref"):
        assert forbidden not in template.columns
    for col in ("judge_id", "label", "confidence", "imagery_date", "note"):
        assert (template[col] == "").all()


# ---------------------------------------------------------------------------
# 라벨 검증 (닫힌 라벨셋)
# ---------------------------------------------------------------------------

def test_label_sets_defined_for_all_four_sample_types():
    assert set(judging_08.LABEL_SETS.keys()) == {
        "segment", "candidate", "island_gap", "placeholder",
    }
    for labels in judging_08.LABEL_SETS.values():
        assert "판독불가" in labels


def test_validate_labels_accepts_every_label_in_its_own_closed_set():
    for sample_type, labels in judging_08.LABEL_SETS.items():
        df = pd.DataFrame({
            "pid": [f"P{i}" for i in range(len(labels))],
            "sample_type": [sample_type] * len(labels),
            "label": labels,
        })
        assert judging_08.validate_labels(df) == []


def test_validate_labels_rejects_out_of_set_label_per_type():
    df = pd.DataFrame({
        "pid": ["S001", "S002", "S003"],
        "sample_type": ["segment", "candidate", "placeholder"],
        "label": ["분리형_자전거도로", "물리적_단절", "존재함"],  # 마지막은 세트 밖("실재"가 맞음)
    })
    invalid = judging_08.validate_labels(df)
    assert len(invalid) == 1
    assert invalid[0]["pid"] == "S003"


def test_validate_labels_rejects_label_from_a_different_sample_types_set():
    # "물리적_단절"은 candidate/island_gap 세트지 segment 세트가 아니다.
    df = pd.DataFrame({
        "pid": ["S001"], "sample_type": ["segment"], "label": ["물리적_단절"],
    })
    invalid = judging_08.validate_labels(df)
    assert len(invalid) == 1


def test_validate_labels_ignores_empty_labels():
    df = pd.DataFrame({
        "pid": ["S001"], "sample_type": ["segment"], "label": [""],
    })
    assert judging_08.validate_labels(df) == []


# ---------------------------------------------------------------------------
# 빈 라벨 카운트
# ---------------------------------------------------------------------------

def test_check_empty_labels_counts_by_sample_type():
    df = pd.DataFrame({
        "pid": ["S001", "S002", "S003"],
        "sample_type": ["segment", "segment", "candidate"],
        "label": ["", "분리형_자전거도로", ""],
    })
    counts = judging_08.check_empty_labels(df)
    assert counts == {"segment": 1, "candidate": 1}


def test_check_empty_labels_empty_when_all_filled():
    df = pd.DataFrame({
        "pid": ["S001"], "sample_type": ["segment"], "label": ["시설없음"],
    })
    assert judging_08.check_empty_labels(df) == {}


# ---------------------------------------------------------------------------
# Cohen's kappa
# ---------------------------------------------------------------------------

def test_kappa_perfect_agreement_is_one_overall_and_per_sample_type():
    df_a = pd.DataFrame({
        "pid": ["S001", "S002", "S003", "S004"],
        "sample_type": ["segment", "segment", "candidate", "candidate"],
        "label": ["분리형_자전거도로", "시설없음", "물리적_단절", "공사중_또는_미개통"],
    })
    df_b = df_a.copy()
    kappas = judging_08.compute_kappa(df_a, df_b)
    assert kappas["overall"] == pytest.approx(1.0)
    assert kappas["segment"] == pytest.approx(1.0)
    assert kappas["candidate"] == pytest.approx(1.0)


def test_kappa_disagreement_is_less_than_one():
    df_a = pd.DataFrame({
        "pid": ["S001", "S002", "S003", "S004"],
        "sample_type": ["segment"] * 4,
        "label": ["분리형_자전거도로", "시설없음", "분리형_자전거도로", "시설없음"],
    })
    df_b = pd.DataFrame({
        "pid": ["S001", "S002", "S003", "S004"],
        "sample_type": ["segment"] * 4,
        "label": ["분리형_자전거도로", "분리형_자전거도로", "시설없음", "시설없음"],
    })
    kappas = judging_08.compute_kappa(df_a, df_b)
    assert kappas["overall"] < 1.0


# ---------------------------------------------------------------------------
# sheets: 좌표/URL이 outputs/private 밖으로 새지 않는지
# ---------------------------------------------------------------------------

def test_sheets_writes_only_under_outputs_private(tmp_path):
    root = tmp_path
    private_dir = root / "outputs" / "private"
    private_dir.mkdir(parents=True)
    private_df = _synthetic_private_df(n_segment=5, n_candidate=5, n_island_gap=5, n_placeholder=5)
    private_df.to_csv(private_dir / "sample_points.csv", index=False, encoding="utf-8-sig")

    paths = judging_08.write_judge_sheets(root)

    assert set(paths.keys()) == {"A", "B"}
    for judge_id, path in paths.items():
        assert path.exists()
        assert path.parent == private_dir
        assert path.name == f"judging_sheet_{judge_id}.csv"


def test_sheets_never_write_coordinates_or_urls_outside_private(tmp_path):
    root = tmp_path
    private_dir = root / "outputs" / "private"
    private_dir.mkdir(parents=True)
    private_df = _synthetic_private_df(n_segment=5, n_candidate=5, n_island_gap=5, n_placeholder=5)
    private_df.to_csv(private_dir / "sample_points.csv", index=False, encoding="utf-8-sig")

    judging_08.write_judge_sheets(root)

    for path in root.rglob("*"):
        if path.is_dir() or private_dir == path.parent or private_dir in path.parents:
            continue
        if path.suffix.lower() not in (".csv", ".md", ".txt"):
            continue
        text = path.read_text(encoding="utf-8-sig")
        assert "vworld_url" not in text
        assert "map.vworld.kr" not in text


def test_sheets_shuffle_with_fixed_seeds_and_cover_all_pids():
    root_df = _synthetic_private_df(n_segment=5, n_candidate=5, n_island_gap=5, n_placeholder=5)
    sheet_a1 = judging_08.build_judge_sheet(root_df, "A", judging_08.JUDGE_SEEDS["A"])
    sheet_a2 = judging_08.build_judge_sheet(root_df, "A", judging_08.JUDGE_SEEDS["A"])
    sheet_b = judging_08.build_judge_sheet(root_df, "B", judging_08.JUDGE_SEEDS["B"])

    # 같은 시드는 같은 순서(재현 가능)
    assert list(sheet_a1["pid"]) == list(sheet_a2["pid"])
    # 두 판독자 모두 전체 pid를 하나씩 받는다
    assert set(sheet_a1["pid"]) == set(root_df["pid"])
    assert set(sheet_b["pid"]) == set(root_df["pid"])
    # 시드가 다르면 순서가 달라진다(우연히 같을 확률은 20!분의 1 수준)
    assert list(sheet_a1["pid"]) != list(sheet_b["pid"])
    # judge_id, label 등 판독용 빈 컬럼 + vworld_url이 포함된다
    assert "vworld_url" in sheet_a1.columns
    assert (sheet_a1["judge_id"] == "A").all()
    assert (sheet_a1["label"] == "").all()
    # 판독자가 표본 출처를 추정할 단서(stratum, source_ref)는 시트에 없다
    assert "stratum" not in sheet_a1.columns
    assert "source_ref" not in sheet_a1.columns


# ---------------------------------------------------------------------------
# score: 빈 라벨/잘못된 라벨 거부, 정상 채점
# ---------------------------------------------------------------------------

def _filled_sheet(judge_id, labels):
    return pd.DataFrame({
        "pid": [f"S{i:03d}" for i in range(1, len(labels) + 1)],
        "sample_type": ["segment"] * len(labels),
        "district": ["동탄"] * len(labels),
        "vworld_url": ["https://map.vworld.kr/map/maps.do?lat=0&lon=0&level=18"] * len(labels),
        "judge_id": [judge_id] * len(labels),
        "label": labels,
        "confidence": [2] * len(labels),
        "imagery_date": ["2026-01-01"] * len(labels),
        "note": [""] * len(labels),
        "imagery_source": ["synthetic"] * len(labels),
        "passability": ["판독불가"] * len(labels),
        "target_packet": [f"judging_targets/S{i:03d}.html" for i in range(1, len(labels)+1)],
    })


def test_score_refuses_when_either_sheet_has_empty_labels(tmp_path):
    root = tmp_path
    (root / "outputs" / "private").mkdir(parents=True)
    sheet_a = _filled_sheet("A", ["분리형_자전거도로", "", "시설없음"])
    sheet_b = _filled_sheet("B", ["분리형_자전거도로", "시설없음", "시설없음"])
    path_a = root / "outputs" / "private" / "judging_sheet_A.csv"
    path_b = root / "outputs" / "private" / "judging_sheet_B.csv"
    sheet_a.to_csv(path_a, index=False, encoding="utf-8-sig")
    sheet_b.to_csv(path_b, index=False, encoding="utf-8-sig")

    with pytest.raises(ValueError, match="빈 라벨"):
        judging_08.score(root, path_a, path_b)


def test_score_refuses_on_out_of_set_label(tmp_path):
    root = tmp_path
    (root / "outputs" / "private").mkdir(parents=True)
    sheet_a = _filled_sheet("A", ["분리형_자전거도로", "이상한값", "시설없음"])
    sheet_b = _filled_sheet("B", ["분리형_자전거도로", "시설없음", "시설없음"])
    path_a = root / "outputs" / "private" / "judging_sheet_A.csv"
    path_b = root / "outputs" / "private" / "judging_sheet_B.csv"
    sheet_a.to_csv(path_a, index=False, encoding="utf-8-sig")
    sheet_b.to_csv(path_b, index=False, encoding="utf-8-sig")

    with pytest.raises(ValueError, match="라벨셋"):
        judging_08.score(root, path_a, path_b)


def test_score_writes_agreement_csv_and_numbers(tmp_path):
    root = tmp_path
    (root / "outputs" / "private").mkdir(parents=True)
    sheet_a = _filled_sheet("A", ["분리형_자전거도로", "시설없음", "분리형_자전거도로", "시설없음"])
    sheet_b = _filled_sheet("B", ["분리형_자전거도로", "분리형_자전거도로", "분리형_자전거도로", "시설없음"])
    path_a = root / "outputs" / "private" / "judging_sheet_A.csv"
    path_b = root / "outputs" / "private" / "judging_sheet_B.csv"
    sheet_a.to_csv(path_a, index=False, encoding="utf-8-sig")
    sheet_b.to_csv(path_b, index=False, encoding="utf-8-sig")

    import hashlib, json
    manifest_path = root / "outputs/private/judging_manifest.csv"
    sheet_a[["pid", "sample_type", "district", "vworld_url", "target_packet"]].to_csv(manifest_path, index=False)
    (manifest_path.parent / "judging_manifest.json").write_text(json.dumps({
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}))
    agreement_df = judging_08.score(root, path_a, path_b)

    out_path = root / "outputs" / "judging_agreement.csv"
    assert out_path.exists()
    assert "overall" in set(agreement_df["sample_type"])
    assert "segment" in set(agreement_df["sample_type"])

    from analysis.numbers import read_numbers
    numbers = read_numbers(root / "outputs" / "numbers.csv")
    assert "judging_kappa_overall" in numbers
    assert "judging_kappa_segment" in numbers
    assert "judging_n_disagree" in numbers
    assert numbers["judging_n_disagree"] == "1"
