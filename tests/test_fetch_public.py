"""scripts/00b_fetch_public.py 의 계획(build_plan)만 검증한다 (I2).

네트워크 호출은 절대 하지 않는다 -- build_plan()/print_plan()은 순수 함수다.
main()의 실제 fetch 경로는 여기서 실행하지 않는다.
"""
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "00b_fetch_public.py"

FAKE_ROOT = Path("C:/fake/root")


def _load_module():
    spec = importlib.util.spec_from_file_location("fetch_public_00b", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch_public = _load_module()


def test_plan_covers_every_non_official_manifest_source():
    plan = fetch_public.build_plan(FAKE_ROOT)
    names = {item["name"] for item in plan}
    assert "osm_hwaseong_bike_20260914.json" in names
    assert "osm_roads/roads.json" in names
    assert "osm_poi/stops.json" in names
    assert "admin/hwaseong_hjd_20260701.geojson" in names
    assert any(n.startswith("ghsl/") for n in names)
    assert any("population" in n for n in names)
    assert any("schools" in n for n in names)


def test_overpass_items_carry_endpoint_and_query():
    plan = fetch_public.build_plan(FAKE_ROOT)
    overpass_items = [item for item in plan if item["method"] == "overpass"]
    assert len(overpass_items) == 3
    for item in overpass_items:
        assert item["endpoint"] == fetch_public.OVERPASS_ENDPOINT
        assert isinstance(item["query"], str) and item["query"].strip()


def test_dest_paths_are_under_repo_root_data_raw():
    plan = fetch_public.build_plan(FAKE_ROOT)
    for item in plan:
        assert str(item["dest"]).startswith(str(FAKE_ROOT / "data" / "raw"))


def test_manual_items_do_not_claim_to_be_automated():
    plan = fetch_public.build_plan(FAKE_ROOT)
    manual_items = [item for item in plan if item["method"] == "manual"]
    # GHSL(2 tiles) + population + schools = 4개는 자동화하지 않는다
    assert len(manual_items) == 4
    for item in manual_items:
        assert "url" in item


def test_print_plan_does_not_raise(capsys):
    plan = fetch_public.build_plan(FAKE_ROOT)
    fetch_public.print_plan(plan)
    captured = capsys.readouterr()
    assert "osm_hwaseong_bike_20260914.json" in captured.out
