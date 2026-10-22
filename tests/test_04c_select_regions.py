"""scripts/04c_select_regions.py의 순수 함수(pick_districts, rank)에 대한
합성(synthetic) 테스트 -- final-review I6(d)/(e).

파일명이 숫자로 시작해 일반 import 문법(``import scripts.04c_select_regions``)을
쓸 수 없으므로 importlib로 파일 경로에서 직접 모듈을 불러온다.
"""
import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "04c_select_regions.py"
_spec = importlib.util.spec_from_file_location("select_regions_04c", _SCRIPT_PATH)
select_regions_04c = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = select_regions_04c
_spec.loader.exec_module(select_regions_04c)

pick_districts = select_regions_04c.pick_districts
rank = select_regions_04c.rank


# --- pick_districts (I6d) --------------------------------------------------

def test_pick_districts_normal_case_a_and_b_differ():
    shares = pd.DataFrame({
        "공식단일": [0.8, 0.1, 0.2, 0.3],
        "OSM단일": [0.1, 0.7, 0.2, 0.3],
    }, index=["동탄", "병점", "효행", "만세"])

    a, b = pick_districts(shares)

    assert a == "동탄"  # 공식단일 최댓값
    assert b == "병점"  # OSM단일 최댓값, a와 다름


def test_pick_districts_falls_back_to_second_when_a_equals_top_osm_district():
    # "동탄"이 공식단일도 최대, OSM단일도 최대인 경우 -- b는 그 다음(2위)으로
    # 넘어가야 한다(브리프: "A와 B가 같으면 B는 OSM단일 비중 2위 구").
    shares = pd.DataFrame({
        "공식단일": [0.9, 0.1, 0.2, 0.3],
        "OSM단일": [0.9, 0.05, 0.85, 0.1],
    }, index=["동탄", "병점", "효행", "만세"])

    a, b = pick_districts(shares)

    assert a == "동탄"
    assert b == "효행"  # OSM단일 2위 (1위인 동탄은 이미 a)


# --- rank (I6e) -------------------------------------------------------------

def _elig_row(dong, district, eligible=True, n_school=1, n_bus_stop=1):
    return {
        "dong": dong, "district": district,
        "n_school": n_school, "n_bus_stop": n_bus_stop,
        "n_seg_합의": 20, "n_seg_공식단일": 20, "n_seg_OSM단일": 20,
        "eligible": eligible,
    }


def test_rank_orders_by_unreached_descending_then_population_tiebreak():
    elig = pd.DataFrame([
        _elig_row("동A", "동탄"),
        _elig_row("동B", "동탄"),
        _elig_row("동C", "동탄"),
    ])
    # 동A, 동B는 unreached가 동률(500) -- 인구가 더 큰 쪽(동B)이 먼저 와야
    # 한다. 동C는 unreached가 가장 커서 1위.
    access = pd.DataFrame([
        {"dong": "동A", "version": "union", "kind": "school", "cutoff": 2500, "pop": 1000.0, "pop_reaching": 500.0},
        {"dong": "동B", "version": "union", "kind": "school", "cutoff": 2500, "pop": 2000.0, "pop_reaching": 1500.0},
        {"dong": "동C", "version": "union", "kind": "school", "cutoff": 2500, "pop": 3000.0, "pop_reaching": 1000.0},
    ])

    ranked = rank(elig, access)
    ordered = ranked.sort_values("rank_in_district")["dong"].tolist()

    assert ordered == ["동C", "동B", "동A"]
    assert ranked.set_index("dong").loc["동B", "rank_in_district"] == 2
    assert ranked.set_index("dong").loc["동A", "rank_in_district"] == 3


def test_rank_ineligible_dong_gets_nan_rank_regardless_of_unreached():
    elig = pd.DataFrame([
        _elig_row("동A", "동탄", eligible=True),
        _elig_row("동B", "동탄", eligible=False),
    ])
    access = pd.DataFrame([
        {"dong": "동A", "version": "union", "kind": "school", "cutoff": 2500, "pop": 1000.0, "pop_reaching": 900.0},
        # 동B가 unreached는 훨씬 크지만 eligible=False라 순위에서 빠져야 한다.
        {"dong": "동B", "version": "union", "kind": "school", "cutoff": 2500, "pop": 1000.0, "pop_reaching": 0.0},
    ])

    ranked = rank(elig, access)

    assert ranked.set_index("dong").loc["동A", "rank_in_district"] == 1
    assert pd.isna(ranked.set_index("dong").loc["동B", "rank_in_district"])


def test_rank_raises_on_dong_missing_from_access_by_dong():
    elig = pd.DataFrame([_elig_row("동A", "동탄")])
    access = pd.DataFrame([], columns=["dong", "version", "kind", "cutoff", "pop", "pop_reaching"])

    with pytest.raises(ValueError, match="동A"):
        rank(elig, access)


def test_rank_adds_detached_and_attached_unreached_columns_when_present():
    # final-review I3: access_by_dong.csv에 pop_detached/pop_attached_unreached가
    # 있으면 rank()가 detached/attached_unreached로 이름 붙여 그대로 실어야 한다.
    elig = pd.DataFrame([_elig_row("동A", "동탄")])
    access = pd.DataFrame([{
        "dong": "동A", "version": "union", "kind": "school", "cutoff": 2500,
        "pop": 1000.0, "pop_reaching": 600.0, "pop_detached": 300.0, "pop_attached_unreached": 100.0,
    }])

    ranked = rank(elig, access)

    row = ranked.set_index("dong").loc["동A"]
    assert row["unreached"] == 400.0
    assert row["detached"] == 300.0
    assert row["attached_unreached"] == 100.0


def test_rank_backfills_detached_columns_with_zero_when_absent():
    # 옛 access_by_dong.csv(컬럼 없음)와의 하위호환.
    elig = pd.DataFrame([_elig_row("동A", "동탄")])
    access = pd.DataFrame([{
        "dong": "동A", "version": "union", "kind": "school", "cutoff": 2500,
        "pop": 1000.0, "pop_reaching": 600.0,
    }])

    ranked = rank(elig, access)

    row = ranked.set_index("dong").loc["동A"]
    assert row["detached"] == 0.0
    assert row["attached_unreached"] == 400.0
