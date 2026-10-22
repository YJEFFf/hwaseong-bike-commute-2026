"""Audit counterexamples, synthetic only: no real human ratings or city estimates."""
import importlib.util
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, box
from analysis.routing import RouteFeature, build_access_network, geometry_hash, normalize_features
from analysis.priority import select_length_budget, bundle_gain
from analysis.judgments import compile_decisions, apply_corrections, validate_matching_ids
from analysis.judging_packet import create_manifest, validate_completed_sheet, read_manifest
from analysis.sampling import cohen_kappa
from analysis.ledgers import s2_wide_existing_area
from analysis.population import dasymetric_points

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/"scripts"/(name+".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bundle_reroute_includes_synergy_not_or_of_individual_masks():
    fs = [RouteFeature(str(i), LineString([(a, 0), (b, 0)]))
          for i, (a, b) in enumerate([(0, 10), (60, 70), (120, 130)])]
    net = build_access_network(fs, [[0, 0]], [[130, 0]], access_max=0)
    a, b, c, d = net.endpoint_indices([[10, 0], [60, 0], [70, 0], [120, 0]], .01)
    links = [(a, b, 50), (c, d, 50)]
    assert not bundle_gain(net, links[:1], 130).any()
    assert not bundle_gain(net, links[1:], 130).any()
    assert bundle_gain(net, links, 130).tolist() == [True]


@pytest.mark.parametrize("rule", ["short", "reach", "bottom20"])
def test_selection_never_exceeds_common_length_cap_even_at_ties(rule):
    lengths, scores = {1: 40, 2: 40, 3: 60, 4: 200}, {1: 10, 2: 10, 3: 10, 4: 100}
    selected, used = select_length_budget([4, 3, 2, 1], lengths, scores, 100, rule)
    assert selected == [1, 2] and used == 80
    assert select_length_budget([1, 2, 3, 4], lengths, scores, 100, rule) == (selected, used)


def test_zero_individual_scores_not_filtered_before_bundle_evaluation():
    assert select_length_budget([0, 1], {0: 50, 1: 50}, {0: 0, 1: 0}, 100, "reach")[0] == [0, 1]


def test_kappa_undefined_single_category_and_empty_do_not_crash():
    assert np.isnan(cohen_kappa(["a", "a"], ["a", "a"]))
    assert np.isnan(cohen_kappa([], []))
    with pytest.raises(ValueError):
        cohen_kappa(["a"], [])


@pytest.mark.parametrize("other", [["a"], ["a", "a"], ["a", "c"]])
def test_missing_duplicate_or_unexpected_ids_are_rejected(other):
    with pytest.raises(ValueError):
        validate_matching_ids(pd.DataFrame({"pid": ["a", "b"]}), pd.DataFrame({"pid": other}))


def sample(kind="segment", geom=None):
    geom = geom if geom is not None else LineString([(40, 0), (60, 0)])
    return pd.DataFrame([dict(pid="S001", sample_type=kind, district="synthetic",
        source_origin="official", target_wkt=geom.wkt, vworld_url="https://example.com/imagery")])


def decisions(label="시설없음", passability="통행불가", **extras):
    return pd.DataFrame([dict(pid="S001", final_label=label, passability=passability,
                             reason="synthetic test evidence", reviewed_by="synthetic A+B", **extras)])


def test_remove_only_observed_subsegment_and_leave_other_parallel_source():
    source = RouteFeature("official:1", LineString([(0, 0), (100, 0)]), source="official")
    parallel = RouteFeature("osm:2", LineString([(0, 5), (100, 5)]), source="osm")
    manifest = compile_decisions(sample(), decisions(), [source, parallel])
    corrected, summary = apply_corrections([source, parallel], manifest)
    assert sum(f.geometry.length for f in corrected) == pytest.approx(180)
    assert parallel in corrected
    net = build_access_network(corrected[:2], [[0, 0]], [[100, 0]], access_max=0)
    assert np.isinf(net.approach_distances()[0])
    assert summary["coverage"] == "partial_sample_only"


def test_changed_source_hash_rejects_stale_corrections():
    source = RouteFeature("official:1", LineString([(0, 0), (100, 0)]), source="official")
    manifest = compile_decisions(sample(), decisions(), [source])
    altered = RouteFeature("official:1", LineString([(0, 0), (101, 0)]), source="official")
    with pytest.raises(ValueError, match="stale"):
        apply_corrections([altered], manifest)


def test_partial_removal_preserves_unaffected_bridge_node_refs():
    source = RouteFeature("official:1", LineString([(0, 0), (100, 0)]),
                          source="official", node_refs=(1, 2))
    bridge = RouteFeature("bridge", LineString([(100, 0), (200, 0)]),
                          level="1", lateral_access=False, node_refs=(2, 3))
    exit_road = RouteFeature("exit", LineString([(200, 0), (300, 0)]), node_refs=(3, 4))
    payload = compile_decisions(sample(), decisions(), [source, bridge, exit_road])
    result, _ = apply_corrections([source, bridge, exit_road], payload)
    net = build_access_network(result, [[80, 0]], [[300, 0]], access_max=0)
    assert net.approach_distances()[0] == pytest.approx(220)


def test_unknown_does_not_certify_or_delete():
    source = RouteFeature("official:1", LineString([(0, 0), (100, 0)]), source="official")
    manifest = compile_decisions(sample(), decisions("판독불가", "판독불가"), [source])
    result, _ = apply_corrections([source], manifest)
    assert result == [source] and manifest["operations"][0]["action"] == "unresolved"


def test_final_label_set_and_contradiction_validation():
    with pytest.raises(ValueError, match="invalid final_label"):
        compile_decisions(sample(), decisions("anything"), [])
    with pytest.raises(ValueError, match="contradictory"):
        compile_decisions(sample("candidate"), decisions("물리적_단절", "통행가능"), [])


def test_gap_confirmation_requires_actual_path_and_applies_to_routing():
    fs = [RouteFeature("a", LineString([(0, 0), (40, 0)])),
          RouteFeature("b", LineString([(60, 0), (100, 0)]))]
    final = decisions("실제로는_연결됨(기록만_끊김)", "통행가능")
    with pytest.raises(ValueError, match="connection_wkt"):
        compile_decisions(sample("candidate"), final, fs)
    final["connection_wkt"] = "LINESTRING (40 0, 50 10, 60 0)"
    manifest = compile_decisions(sample("candidate"), final, fs)
    corrected, _ = apply_corrections(fs, manifest)
    before = build_access_network(fs, [[0, 0]], [[100, 0]], access_max=0)
    after = build_access_network(corrected, [[0, 0]], [[100, 0]], access_max=0)
    assert np.isinf(before.approach_distances()[0])
    assert after.approach_distances()[0] == pytest.approx(80 + 20*np.sqrt(2))


def test_polygon_presence_never_invents_a_centerline():
    manifest = compile_decisions(sample("placeholder", box(0, 0, 10, 10)),
                                 decisions("실재", "통행가능"), [])
    assert manifest["operations"][0]["action"] == "observation_only"
    assert apply_corrections([], manifest)[0] == []


def test_blind_manifest_random_id_is_frozen_and_geometry_card_private(tmp_path):
    frame = sample()
    first = create_manifest(frame, tmp_path)
    second = create_manifest(frame, tmp_path)
    assert first.pid.tolist() == second.pid.tolist()
    assert first.pid[0].startswith("P-") and first.pid[0] != "S001"
    card = (tmp_path/first.target_packet[0]).read_text()
    assert "<svg" in card and "official" not in card and "S001" not in card
    assert 'data-role="target-border"' in card
    assert 'data-role="target-geometry"' in card
    assert "판독 대상 기하" in card
    assert "실제 시설 폭이 아닙니다" in card
    assert "A/B는 대상의 양끝이나 등급이 아니라 판독자 구분" in card
    assert "시점" in card and "종점" in card
    changed = frame.copy()
    changed["target_wkt"] = "LINESTRING (0 0, 200 0)"
    with pytest.raises(ValueError, match="sample changed"):
        create_manifest(changed, tmp_path)


def test_midpoint_only_packet_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="target geometry"):
        create_manifest(sample().drop(columns="target_wkt"), tmp_path)


def test_tampering_manifest_is_detected(tmp_path):
    create_manifest(sample(), tmp_path)
    path = tmp_path/"judging_manifest.csv"
    path.write_bytes(path.read_bytes()+b"\n")
    with pytest.raises(ValueError, match="modified"):
        read_manifest(tmp_path)


def test_completed_sheet_requires_confidence_source_date_and_full_coverage(tmp_path):
    manifest = create_manifest(sample(), tmp_path)
    frame = manifest[["pid", "sample_type", "district", "vworld_url", "target_packet"]].assign(
        judge_id="A", confidence=2, imagery_date="unknown", imagery_source="synthetic",
        passability="판독불가")
    validate_completed_sheet(frame, manifest, "A")
    for col, bad in [("confidence", 4), ("imagery_date", ""), ("imagery_source", ""), ("passability", "")]:
        wrong = frame.copy()
        wrong[col] = bad
        with pytest.raises(ValueError):
            validate_completed_sheet(wrong, manifest, "A")


def test_non_simple_line_split_preserves_length_direction_and_refs():
    line = LineString([(0, 0), (100, 100), (0, 100), (100, 0)])
    source = RouteFeature("x", line, direction=1, node_refs=(1, 2, 3, 4))
    parts = normalize_features([source])
    assert len(parts) == 3 and all(p.geometry.is_simple for p in parts)
    assert all(p.direction == 1 for p in parts)
    assert parts[1].node_refs == (2, 3)
    assert sum(p.geometry.length for p in parts) == pytest.approx(line.length)


def test_canopy_area_dedupes_after_clipping_and_does_not_claim_min_width():
    poly = box(0, 0, 100, 5)
    area = s2_wide_existing_area([poly, poly], box(0, -1, 200, 10))
    assert area["area_m2"] == 500
    assert "NOT minimum width" in area["meaning"]


def test_positive_population_without_boundary_or_raster_fails():
    with pytest.raises(ValueError, match="boundary"):
        dasymetric_points([], {}, {"A": 100})
    with pytest.raises(ValueError, match="raster coverage"):
        dasymetric_points([], {"A": box(0, 0, 1, 1)}, {"A": 100})


def test_priority_script_synthetic_integration_and_fixed_groups(tmp_path, monkeypatch):
    module = script("05_priority")
    out = tmp_path/"outputs"
    out.mkdir()
    pd.DataFrame({"x": [0., 0.], "y": [0., 10.], "pop": [80., 20.], "dong": ["A", "A"]}).to_csv(out/"origins_5186.csv", index=False)
    pd.DataFrame({"x": [2000.], "y": [0.], "kind": ["초등학교"]}).to_csv(out/"destinations_5186.csv", index=False)
    fs = [RouteFeature(str(i), LineString([(a, 0), (b, 0)]))
          for i, (a, b) in enumerate([(0, 500), (550, 1000), (1050, 2000)])]
    monkeypatch.setattr(module, "load_features", lambda *args: fs)
    monkeypatch.setattr(module, "region_polygons", lambda *args: {1: box(-10, -10, 2100, 20), 2: box(3000, 3000, 4000, 4000)})
    result = module.run(tmp_path, ["A", "B"], quick=True)
    assert len(result) == 6
    rows = result[result.region.eq(1)]
    assert rows.gained_pop.eq(100).all()
    assert rows.used_length_m.le(rows.length_budget_m + 1e-8).all()
    groups = pd.read_csv(out/"priority_fixed_group.csv")
    assert groups.loc[0, "bottom_group_pop"] == 20
    assert json.loads((out/"priority_method.json").read_text())["scenario_count"] == 1
