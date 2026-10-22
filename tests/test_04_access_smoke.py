"""scripts/04_access.py의 run_analysis에 대한 합성(synthetic) 스모크 테스트
(final-review I6, "welcome if cheap"). 진짜 원자료 대신 아주 작은 합성
repo_root(tmp_path)를 만들어 전체 파이프라인이 끝까지 돌고, I3의 핵심
불변식(detached + attached_unreached + reaching == pop, 행 단위)과
union >= osm/official 슈퍼셋 성질(M3/I6c와 동일한 취지)을 지키는지만
확인한다 -- 수치 자체의 정확성은 tests/test_access.py의 순수 함수
테스트들이 이미 따로 검증한다.

파일명이 숫자로 시작해 일반 import 문법을 쓸 수 없으므로 importlib로
scripts/04_access.py를 직접 불러온다.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "04_access.py"
_spec = importlib.util.spec_from_file_location("access_04", _SCRIPT_PATH)
access_04 = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = access_04
_spec.loader.exec_module(access_04)


@pytest.fixture
def synthetic_repo(tmp_path):
    root = tmp_path
    (root / "outputs").mkdir()
    (root / "data" / "raw" / "population").mkdir(parents=True)
    (root / "data" / "raw" / "osm_roads").mkdir(parents=True)

    # origins: 4개 구(동탄/병점/효행/만세)에 하나씩 + 어디서도 150m 이내가
    # 아닌 "detached" origin 하나(가상동1, 동탄에 속함).
    origins = pd.DataFrame({
        "x": [0.0, 100.0, 0.0, 100.0, 5000.0],
        "y": [5.0, 5.0, 6.0, 6.0, 5000.0],
        "pop": [100.0, 200.0, 10.0, 10.0, 50.0],
        "dong": ["가상동1", "가상동2", "가상동3", "가상동4", "가상동1"],
    })
    origins.to_csv(root / "outputs" / "origins_5186.csv", index=False, encoding="utf-8-sig")

    destinations = pd.DataFrame({
        "name": ["가상초", "가상정류장", "가상역"],
        "kind": ["초등학교", "bus_stop", "station"],
        "x": [0.0, 100.0, 100.0],
        "y": [0.0, 0.0, 0.0],
    })
    destinations.to_csv(root / "outputs" / "destinations_5186.csv", index=False, encoding="utf-8-sig")

    # 인구 CSV: dong_district_map이 요구하는 3컬럼(시군구명/읍면동명/계),
    # 4개 구 전부 인구>0 -- 그래야 M9(구 인구 0이면 fail-fast)에 걸리지 않는다.
    pop_df = pd.DataFrame({
        "시군구명": ["화성시 동탄구", "화성시 만세구", "화성시 병점구", "화성시 효행구"],
        "읍면동명": ["가상동1", "가상동2", "가상동3", "가상동4"],
        "계": [150, 200, 10, 10],
    })
    pop_df.to_csv(root / "data" / "raw" / "population" / "pop_raw.bin", index=False, encoding="cp949")

    official_fc = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature", "properties": {},
            "geometry": {"type": "LineString", "coordinates": [[0.0, 0.0], [100.0, 0.0]]},
        }],
    }
    (root / "data" / "raw" / "화성_자전거노선_5186.geojson").write_text(
        json.dumps(official_fc, ensure_ascii=False), encoding="utf-8"
    )

    # OSM: 공식 노선과 무관한 먼 곳에 있는 별도 way 하나 (실제로 도달성에는
    # 기여하지 않지만, union/osm 그래프 빌드 경로 자체를 실행해 본다).
    osm_json = {
        "elements": [{
            "type": "way", "tags": {"highway": "cycleway"},
            "geometry": [{"lat": 37.20, "lon": 126.83}, {"lat": 37.201, "lon": 126.831}],
        }],
    }
    (root / "data" / "raw" / "osm_hwaseong_bike_20260914.json").write_text(
        json.dumps(osm_json, ensure_ascii=False), encoding="utf-8"
    )

    roads_json = {"elements": []}
    (root / "data" / "raw" / "osm_roads" / "roads.json").write_text(
        json.dumps(roads_json, ensure_ascii=False), encoding="utf-8"
    )

    return root


def test_run_analysis_smoke_end_to_end(synthetic_repo):
    out = access_04.run_analysis(synthetic_repo)

    assert list(out.columns) == [
        "dong", "district", "pop", "version", "kind", "cutoff",
        "pop_reaching", "pop_detached", "pop_attached_unreached",
    ]
    assert len(out) > 0
    assert (out["pop_reaching"] >= 0).all()
    assert (out["pop_reaching"] <= out["pop"] + 1e-6).all()

    # I3 불변식: 각 (dong, version, kind, cutoff) 행에서 세 인구가 정확히 pop로 합산된다.
    total_check = out["pop_reaching"] + out["pop_detached"] + out["pop_attached_unreached"]
    assert (total_check - out["pop"]).abs().max() < 1e-6

    # union(school, c2500)이 official 단독보다 도달 인구가 적지 않아야 한다
    # (fix round 1의 슈퍼셋 성질, I6c와 같은 취지의 회귀 확인).
    sel = out[(out["kind"] == "school") & (out["cutoff"] == 2500)]
    union_reach = sel[sel["version"] == "union"]["pop_reaching"].sum()
    official_reach = sel[sel["version"] == "official"]["pop_reaching"].sum()
    assert union_reach >= official_reach - 1e-6
