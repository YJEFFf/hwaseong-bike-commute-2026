"""scripts/run_all.py 의 스텝 순서·플래그를 검증 (I1).

subprocess를 전혀 실행하지 않는다 — build_steps()/truncate_at() 은 순수 함수라
스텝 목록을 계산만 하고 아무 것도 실행하지 않는다. main()/run_steps()는 여기서
호출하지 않는다.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_ALL_PATH = REPO_ROOT / "scripts" / "run_all.py"

EXPECTED_ORDER = [
    "00_fetch",
    "01_verify",
    "01b_osm_stats",
    "01c_official_topology",
    "02_agreement",
    "02b_origins_destinations",
    "03_sample",
    "04_access",
    "04b_lowstress_stats",
    "04c_select_regions",
    "05_priority",
    "06_carbon",
    "07_figures",
    "render_report",
]

FAKE_ROOT = Path("C:/fake/root") if sys.platform == "win32" else Path("/fake/root")
REGIONS = "향남읍,동탄6동"


def _load_run_all():
    spec = importlib.util.spec_from_file_location("run_all", RUN_ALL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_all = _load_run_all()


def test_step_order_matches_pipeline_with_fetch():
    steps = run_all.build_steps(FAKE_ROOT, fetch=True)
    assert [s["name"] for s in steps] == EXPECTED_ORDER


def test_step_order_matches_pipeline_without_fetch():
    steps = run_all.build_steps(FAKE_ROOT, fetch=False)
    assert [s["name"] for s in steps] == EXPECTED_ORDER


def test_00_fetch_only_runs_with_fetch_flag():
    steps_no_fetch = {s["name"]: s for s in run_all.build_steps(FAKE_ROOT, fetch=False)}
    steps_fetch = {s["name"]: s for s in run_all.build_steps(FAKE_ROOT, fetch=True)}

    assert steps_no_fetch["00_fetch"]["run"] is False
    assert steps_fetch["00_fetch"]["run"] is True


def test_every_other_step_always_runs_regardless_of_fetch_flag():
    steps_no_fetch = {s["name"]: s for s in run_all.build_steps(FAKE_ROOT, fetch=False)}
    steps_fetch = {s["name"]: s for s in run_all.build_steps(FAKE_ROOT, fetch=True)}

    for name in EXPECTED_ORDER:
        if name == "00_fetch":
            continue
        assert steps_no_fetch[name]["run"] is True
        assert steps_fetch[name]["run"] is True


def test_flags_match_each_scripts_argparse():
    steps = {s["name"]: s for s in run_all.build_steps(FAKE_ROOT, fetch=True)}

    assert steps["00_fetch"]["args"] == []
    assert steps["01_verify"]["args"] == []
    assert steps["01b_osm_stats"]["args"] == []
    assert steps["01c_official_topology"]["args"] == []
    assert steps["02_agreement"]["args"] == []
    assert steps["02b_origins_destinations"]["args"] == [
        "--raw",
        str(FAKE_ROOT / "data" / "raw"),
    ]
    assert steps["03_sample"]["args"] == ["--repo-root", str(FAKE_ROOT)]
    assert steps["04_access"]["args"] == ["--repo-root", str(FAKE_ROOT)]
    assert steps["04b_lowstress_stats"]["args"] == ["--repo-root", str(FAKE_ROOT)]
    assert steps["04c_select_regions"]["args"] == ["--repo-root", str(FAKE_ROOT)]
    assert steps["05_priority"]["args"] == [
        "--repo-root",
        str(FAKE_ROOT),
        "--regions",
        REGIONS,
    ]
    assert steps["06_carbon"]["args"] == [
        "--repo-root",
        str(FAKE_ROOT),
        "--regions",
        REGIONS,
    ]


def test_05_priority_and_06_carbon_use_the_selected_regions():
    steps = {s["name"]: s for s in run_all.build_steps(FAKE_ROOT, fetch=True)}
    # --regions는 두 동을 콤마로 합친 하나의 토큰이다 ("향남읍,동탄6동"), 별도 인자가 아니다.
    assert REGIONS in steps["05_priority"]["args"]
    assert REGIONS in steps["06_carbon"]["args"]
    assert "향남읍" in REGIONS and "동탄6동" in REGIONS


def test_step_scripts_point_under_the_given_repo_root():
    steps = run_all.build_steps(FAKE_ROOT, fetch=True)
    for s in steps:
        assert s["script"] == FAKE_ROOT / "scripts" / f"{s['name']}.py"


def test_until_truncates_after_named_step():
    steps = run_all.build_steps(FAKE_ROOT, fetch=True)
    truncated = run_all.truncate_at(steps, "05_priority")
    assert [s["name"] for s in truncated] == EXPECTED_ORDER[:EXPECTED_ORDER.index("05_priority")+1]


def test_until_at_first_step_keeps_only_that_step():
    steps = run_all.build_steps(FAKE_ROOT, fetch=True)
    truncated = run_all.truncate_at(steps, "00_fetch")
    assert [s["name"] for s in truncated] == ["00_fetch"]


def test_until_unknown_step_raises_system_exit():
    steps = run_all.build_steps(FAKE_ROOT, fetch=True)
    with pytest.raises(SystemExit):
        run_all.truncate_at(steps, "07_nonexistent_step")


def test_until_none_keeps_every_step():
    steps = run_all.build_steps(FAKE_ROOT, fetch=True)
    assert run_all.truncate_at(steps, None) == steps


def test_06_carbon_step_present_even_though_script_does_not_exist_yet():
    """06_carbon.py는 아직 이 브랜치에 없다 (Task 15b가 추가 예정) — 그래도
    스텝 목록에는 있어야 한다. 이 테스트는 파일 존재 여부를 확인하지 않는다
    (신설 전이라 실패하면 안 됨), 목록에 이름이 있는지만 본다."""
    steps = run_all.build_steps(FAKE_ROOT, fetch=True)
    assert "06_carbon" in [s["name"] for s in steps]


def test_missing_inputs_never_delete_existing_numbers_or_create_run(tmp_path):
    import json
    (tmp_path/"outputs").mkdir()
    numbers = tmp_path/"outputs/numbers.csv"
    numbers.write_text("original results")
    (tmp_path/"data_manifest.json").write_text(json.dumps({"raw_inputs": [{"path": "data/raw/missing.json"}]}))
    with pytest.raises(FileNotFoundError, match="existing outputs unchanged"):
        run_all.execute(tmp_path)
    assert numbers.read_text() == "original results"
    assert not (tmp_path/"outputs/runs").exists()


def test_unknown_until_never_changes_existing_outputs(tmp_path):
    with pytest.raises(SystemExit):
        run_all.execute(tmp_path, until="typo")
    assert not list(tmp_path.iterdir())


def _runner_fixture(tmp_path):
    import json
    (tmp_path/"outputs").mkdir()
    (tmp_path/"outputs/numbers.csv").write_text("original results")
    (tmp_path/"data_manifest.json").write_text(json.dumps({"raw_inputs": []}))
    for name in ("analysis", "scripts", "params", "docs", "validation"):
        (tmp_path/name).mkdir()
        (tmp_path/name/"fixture.txt").write_text("synthetic runner-only fixture")
    return tmp_path


def test_failed_run_is_isolated_and_keeps_previous_latest(tmp_path, monkeypatch):
    root = _runner_fixture(tmp_path)
    (root/"outputs/LATEST_RUN.txt").write_text("previous")
    def fail(steps):
        stage = steps[0]["script"].parents[1]
        (stage/"outputs").mkdir(exist_ok=True)
        (stage/"outputs/numbers.csv").write_text("partial results")
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr(run_all, "run_steps", fail)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        run_all.execute(root)
    import json
    manifest = next((root/"outputs/runs").glob("*/run_manifest.json"))
    assert json.loads(manifest.read_text())["status"] == "failed"
    assert (root/"outputs/numbers.csv").read_text() == "original results"
    assert (root/"outputs/LATEST_RUN.txt").read_text() == "previous"


def test_success_only_updates_pointer_not_historical_results(tmp_path, monkeypatch):
    root = _runner_fixture(tmp_path)
    monkeypatch.setattr(run_all, "run_steps", lambda steps: None)
    result = run_all.execute(root)
    assert (root/"outputs/numbers.csv").read_text() == "original results"
    assert (root/"outputs/LATEST_RUN.txt").read_text().strip() == str(result.relative_to(root))
    import json
    assert json.loads((result/"run_manifest.json").read_text())["status"] == "complete_provisional"


def test_prepared_mode_skips_raw_population_but_keeps_graph_inputs(tmp_path):
    import json
    paths = ["data/raw/population/pop_raw.bin", "data/raw/ghsl/tile.tif",
             "data/raw/osm_roads/roads.json", "data/raw/admin/boundary.geojson"]
    (tmp_path/"data_manifest.json").write_text(json.dumps({"raw_inputs": [{"path": p} for p in paths]}))
    requested = run_all.required_inputs(tmp_path, prepared=True)
    assert paths[0] not in requested and paths[1] not in requested
    assert paths[2] in requested and paths[3] in requested
    assert "outputs/origins_5186.csv" in requested


def test_existing_sample_is_reused_not_overwritten(tmp_path):
    path = tmp_path/"outputs/private/sample_points.csv"
    path.parent.mkdir(parents=True)
    path.write_text("frozen")
    steps = {s["name"]: s for s in run_all.build_steps(tmp_path)}
    assert not steps["03_sample"]["run"]
    assert path.read_text() == "frozen"
