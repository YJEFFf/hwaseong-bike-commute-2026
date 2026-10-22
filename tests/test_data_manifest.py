"""I2 — data_manifest.json 의 raw_inputs 항목이 필수 필드를 모두 갖는지 검증.

이 테스트는 네트워크에 접근하지 않고, 이미 커밋된 data_manifest.json 만 읽는다.
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "data_manifest.json"

REQUIRED_FIELDS = ["path", "sha256", "bytes", "source", "url", "retrieved", "licence", "query"]

# I2 판정문에 열거된, 파이프라인이 실제로 쓰는 raw 입력 전부.
EXPECTED_PATHS = {
    "data/raw/화성_자전거노선_5186.geojson",
    "data/raw/화성_자전거도로면_5186.geojson",
    "data/raw/osm_hwaseong_bike_20260914.json",
    "data/raw/osm_roads/roads.json",
    "data/raw/osm_poi/stops.json",
    "data/raw/admin/hwaseong_hjd_20260701.geojson",
    "data/raw/ghsl/GHS_POP_E2025_GLOBE_R2023A_54009_100_V1_0_R5_C29.tif",
    "data/raw/ghsl/GHS_POP_E2025_GLOBE_R2023A_54009_100_V1_0_R5_C30.tif",
    "data/raw/population/pop_raw.bin",
    "data/raw/schools/page_1.json",
    "data/raw/schools/page_2.json",
    "data/raw/yejun08_candidates.csv",
}

# 판정문상 Overpass 쿼리 텍스트가 있어야 하는 항목.
OVERPASS_PATHS = {
    "data/raw/osm_hwaseong_bike_20260914.json",
    "data/raw/osm_roads/roads.json",
    "data/raw/osm_poi/stops.json",
}


def _load_manifest():
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_manifest_has_raw_inputs_list():
    manifest = _load_manifest()
    assert "raw_inputs" in manifest
    assert isinstance(manifest["raw_inputs"], list)
    assert len(manifest["raw_inputs"]) > 0


def test_every_pipeline_raw_input_is_covered():
    manifest = _load_manifest()
    paths = {entry["path"] for entry in manifest["raw_inputs"]}
    missing = EXPECTED_PATHS - paths
    assert not missing, f"data_manifest.json에 빠진 raw 입력: {missing}"


def test_raw_input_paths_are_unique():
    manifest = _load_manifest()
    paths = [entry["path"] for entry in manifest["raw_inputs"]]
    assert len(paths) == len(set(paths))


def test_each_raw_input_has_required_fields():
    manifest = _load_manifest()
    for entry in manifest["raw_inputs"]:
        for field in REQUIRED_FIELDS:
            assert field in entry, f"{entry.get('path')}: '{field}' 필드 없음"


def test_each_raw_input_core_fields_are_non_empty():
    manifest = _load_manifest()
    core_fields = ["path", "sha256", "source", "url", "retrieved", "licence"]
    for entry in manifest["raw_inputs"]:
        for field in core_fields:
            value = entry[field]
            assert isinstance(value, str) and value.strip(), (
                f"{entry.get('path')}: '{field}' 가 비어 있음"
            )


def test_each_raw_input_sha256_is_well_formed():
    manifest = _load_manifest()
    for entry in manifest["raw_inputs"]:
        sha = entry["sha256"]
        assert len(sha) == 64, f"{entry['path']}: sha256 길이가 64가 아님 ({len(sha)})"
        int(sha, 16)  # hex 가 아니면 예외


def test_each_raw_input_bytes_is_positive_int():
    manifest = _load_manifest()
    for entry in manifest["raw_inputs"]:
        assert isinstance(entry["bytes"], int) and entry["bytes"] > 0, (
            f"{entry['path']}: bytes 가 양의 정수가 아님"
        )


def test_each_raw_input_retrieved_is_iso_date():
    manifest = _load_manifest()
    for entry in manifest["raw_inputs"]:
        retrieved = entry["retrieved"]
        # YYYY-MM-DD 형식만 허용 (파싱 가능해야 함)
        from datetime import date

        date.fromisoformat(retrieved)


def test_overpass_sourced_inputs_carry_query_text():
    manifest = _load_manifest()
    by_path = {entry["path"]: entry for entry in manifest["raw_inputs"]}
    for path in OVERPASS_PATHS:
        entry = by_path[path]
        assert isinstance(entry["query"], str) and entry["query"].strip(), (
            f"{path}: Overpass 파일인데 query 텍스트가 없음"
        )


def test_non_overpass_inputs_have_null_query():
    manifest = _load_manifest()
    for entry in manifest["raw_inputs"]:
        if entry["path"] not in OVERPASS_PATHS:
            assert entry["query"] is None, f"{entry['path']}: Overpass가 아닌데 query가 설정됨"


def test_flagged_licences_mention_confirmation_needed():
    """admdongkor·MOIS·표준데이터처럼 라이선스가 불확실한 항목은 그 사실을 명시해야 한다."""
    manifest = _load_manifest()
    by_path = {entry["path"]: entry for entry in manifest["raw_inputs"]}

    admin_entry = by_path["data/raw/admin/hwaseong_hjd_20260701.geojson"]
    assert "확인" in admin_entry["licence"] or "미확인" in admin_entry["licence"] or "플래그" in admin_entry["licence"]

    pop_entry = by_path["data/raw/population/pop_raw.bin"]
    assert "미확인" in pop_entry["licence"] or "확인 필요" in pop_entry["licence"]


def test_existing_official_manifest_fields_untouched():
    """01_verify.py 가 계속 쓰는 최상위 필드는 raw_inputs 추가로 사라지면 안 된다."""
    manifest = _load_manifest()
    assert manifest["lines"] == 281
    assert manifest["polys"] == 5978
    assert abs(manifest["line_km"] - 318.982) < 1e-6
    assert "lines_hash" in manifest and "polys_hash" in manifest
    assert manifest["sources"]["lines"] == "화성_자전거노선_5186.geojson"
    assert manifest["sources"]["polys"] == "화성_자전거도로면_5186.geojson"
