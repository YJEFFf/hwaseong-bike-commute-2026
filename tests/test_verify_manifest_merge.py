"""scripts/01_verify.py 가 data_manifest.json을 덮어쓰지 않고 병합하는지 검증
(I1/I2: 01_verify가 실행될 때마다 raw_inputs 같은 다른 최상위 키가 사라지면
안 된다). 네트워크나 실제 원자료 파일에는 접근하지 않는다 — _load_existing_manifest()
와 병합 로직만 직접 호출한다.
"""
import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFY_PATH = REPO_ROOT / "scripts" / "01_verify.py"


def _load_verify_module():
    spec = importlib.util.spec_from_file_location("verify_01", VERIFY_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify_01 = _load_verify_module()


def test_load_existing_manifest_returns_empty_dict_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(verify_01, "MANIFEST_PATH", tmp_path / "does_not_exist.json")
    assert verify_01._load_existing_manifest() == {}


def test_load_existing_manifest_returns_empty_dict_on_invalid_json(tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(verify_01, "MANIFEST_PATH", bad)
    assert verify_01._load_existing_manifest() == {}


def test_load_existing_manifest_preserves_extra_top_level_keys(tmp_path, monkeypatch):
    manifest_path = tmp_path / "data_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "lines": 1,
                "polys": 2,
                "raw_inputs": [{"path": "data/raw/foo.json"}],
                "raw_inputs_schema_note": "note",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(verify_01, "MANIFEST_PATH", manifest_path)

    loaded = verify_01._load_existing_manifest()

    assert loaded["raw_inputs"] == [{"path": "data/raw/foo.json"}]
    assert loaded["raw_inputs_schema_note"] == "note"

    # main()이 하는 것과 같은 종류의 갱신: verified 필드만 덮어써야 한다.
    loaded.update({"lines": 281, "polys": 5978})
    assert loaded["raw_inputs"] == [{"path": "data/raw/foo.json"}]
    assert loaded["lines"] == 281
    assert loaded["polys"] == 5978
