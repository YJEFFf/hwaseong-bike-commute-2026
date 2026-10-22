"""Synthetic safety/geometry tests for the automatic scenario adapter."""
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, Polygon

from analysis.auto_scenarios import (compile_scenarios, exact_interval, fixed_anchor_points,
                                     map_gap_links, read_auto_table, retained_pieces)
from analysis.routing import RouteFeature, build_access_network


def frame(kind='segment', state='unresolved', geom=None, road_ids=''):
    geom = geom if geom is not None else LineString([(40, 0), (60, 0)])
    return pd.DataFrame([dict(pid='P-test', geometry_group='test', sample_type=kind,
        auto_class=state, geometry=geom, target_wkt=geom.wkt, district='test',
        judge_id='AUTO_VECTOR_V1', osm_road_path_ids=road_ids)])


def test_exact_extent_not_entire_line_and_no_buffer_deletion():
    source = RouteFeature('source', LineString([(0, 0), (100, 0)]))
    target = LineString([(40, 0), (60, 0)])
    assert exact_interval(source, target) == (40., 60.)
    assert exact_interval(source, LineString([(40, 1), (60, 1)])) is None
    pieces = retained_pieces(source, [(40, 60)])
    assert sum(p.geometry.length for p in pieces) == 80.


def test_partial_parts_keep_direction_level_and_node_references():
    source = RouteFeature('source', LineString([(0, 0), (30, 0), (100, 0)]),
                          direction=1, level='1', node_refs=(1, 2, 3))
    pieces = retained_pieces(source, [(40, 60)])
    assert all(p.direction == 1 and p.level == '1' for p in pieces)
    assert pieces[0].node_refs == (1, 2, None)
    assert pieces[1].node_refs == (None, 3)


def test_overlapping_removals_not_double_counted():
    source = RouteFeature('source', LineString([(0, 0), (100, 0)]))
    assert sum(p.geometry.length for p in retained_pieces(source, [(20, 50), (30, 70)])) == 50


def test_unknown_restored_only_in_uncertainty_scenario():
    source = RouteFeature('source', LineString([(0, 0), (100, 0)]))
    scenarios, ledger = compile_scenarios([source], [], frame())
    assert sum(f.geometry.length for f in scenarios['auto_base']) == 80
    assert sum(f.geometry.length for f in scenarios['auto_expanded']) == 80
    assert sum(f.geometry.length for f in scenarios['auto_unknown_restored']) == 100
    assert 'withhold_exact_sample' in set(ledger.action)


def test_possible_in_expanded_not_base():
    source = RouteFeature('source', LineString([(0, 0), (100, 0)]))
    scenarios, _ = compile_scenarios([source], [], frame(state='possible'))
    assert sum(f.geometry.length for f in scenarios['auto_base']) == 80
    assert sum(f.geometry.length for f in scenarios['auto_expanded']) == 100


def test_polygon_never_becomes_a_route():
    rows = frame(kind='placeholder', state='supported', geom=Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]))
    scenarios, ledger = compile_scenarios([], [], rows)
    assert all(not values for values in scenarios.values())
    assert set(ledger.action) == {'polygon_observation_only'}


def test_gap_does_not_insert_a_straight_road():
    rows = frame(kind='candidate', state='supported')
    scenarios, ledger = compile_scenarios([], [], rows)
    assert all(not values for values in scenarios.values())
    assert set(ledger.action) == {'gap_observation_no_straight_route_inserted'}


def test_road_addition_is_recorded_geometry_with_direction():
    road = RouteFeature('osm:42:abc', LineString([(40, 0), (50, 10), (60, 0)]), direction=1, source='osm')
    scenarios, _ = compile_scenarios([], [road], frame(kind='candidate', state='possible', road_ids='42'))
    assert not scenarios['auto_base']
    assert scenarios['auto_expanded'][0] == road
    assert scenarios['auto_expanded'][0].direction == 1


def test_fixed_gap_anchors_not_segment_midpoints():
    assert fixed_anchor_points(frame()).shape == (0, 2)
    assert np.array_equal(fixed_anchor_points(frame(kind='candidate')), [[40, 0], [60, 0]])


def test_parallel_gap_excluded_and_missing_endpoints_not_forced():
    source = [RouteFeature('a', LineString([(0, 0), (40, 0)])),
              RouteFeature('b', LineString([(60, 0), (100, 0)]))]
    net = build_access_network(source, [[0, 0]], [[100, 0]], access_max=0)
    links, _ = map_gap_links(net, frame(kind='candidate', state='parallel'))
    assert not links
    links, audit = map_gap_links(net, frame(kind='candidate', geom=LineString([(45, 0), (55, 0)])))
    assert not links and audit.iloc[0].reason == 'unmapped_ground_endpoint'


def test_hypothetical_bundle_connects_without_new_midchord_junction():
    source = [RouteFeature('a', LineString([(0, 0), (40, 0)])),
              RouteFeature('b', LineString([(60, 0), (100, 0)])),
              RouteFeature('crossing', LineString([(50, -20), (50, 20)]))]
    net = build_access_network(source, [[0, 0], [50, -20]], [[100, 0]], access_max=0)
    links, _ = map_gap_links(net, frame(kind='candidate'))
    graph = net.with_links(list(links.values()))
    distances = net.approach_distances(graph=graph)
    assert distances[0] == 100
    assert np.isinf(distances[1])


def test_existing_short_bidirectional_route_not_a_new_project():
    source = [RouteFeature('road', LineString([(0, 0), (40, 0), (60, 0), (100, 0)]))]
    net = build_access_network(source, [[0, 0]], [[100, 0]], access_max=0)
    links, audit = map_gap_links(net, frame(kind='candidate'), reject_existing=True)
    assert not links
    assert audit.iloc[0].reason == 'short_bidirectional_route_already_recorded'


def test_auto_input_rejects_human_sheet_and_duplicate_conflict(tmp_path):
    rows = frame().drop(columns='geometry')
    path = tmp_path/'auto.csv'
    rows.assign(judge_id='A').to_csv(path, index=False)
    with pytest.raises(ValueError, match='AUTO_VECTOR'):
        read_auto_table(path)
    pd.concat([rows, rows.assign(pid='P-other', auto_class='supported')]).to_csv(path, index=False)
    with pytest.raises(ValueError, match='inconsistent'):
        read_auto_table(path)


def test_auto_input_deduplicates_same_target(tmp_path):
    rows = frame(kind='candidate').drop(columns='geometry')
    path = tmp_path/'auto.csv'
    pd.concat([rows, rows.assign(pid='P-other', sample_type='island_gap')]).to_csv(path, index=False)
    assert len(read_auto_table(path)) == 1
