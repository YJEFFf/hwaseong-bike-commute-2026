"""Scientific regression tests derived from the independent audit counterexamples."""
import numpy as np
import pytest
from shapely.geometry import LineString

from analysis.routing import (
    RouteFeature, bicycle_allowed, bicycle_direction, build_access_network, transition_summary,
)


def feature(fid, coords, **kwargs):
    return RouteFeature(fid, LineString(coords), **kwargs)


def test_same_line_vertex_density_does_not_change_access_or_distance():
    origin, dest = [[500, 10]], [[1000, 0]]
    distances = []
    for coords in ([(0, 0), (1000, 0)], [(0, 0), (250, 0), (500, 0), (1000, 0)]):
        net = build_access_network([feature("a", coords)], origin, dest)
        assert not net.detached[0]
        distances.append(net.approach_distances()[0])
    assert distances == pytest.approx([510, 510])


def test_adding_a_nearer_isolated_line_preserves_old_origin_and_destination_access():
    main = feature("main", [(0, 0), (1000, 0)])
    isolated = [feature("o", [(0, 20), (10, 20)]), feature("d", [(1000, 20), (1010, 20)])]
    old = build_access_network([main], [[0, 20]], [[1000, 20]])
    new = build_access_network([main, *isolated], [[0, 20]], [[1000, 20]])
    assert old.approach_distances()[0] == pytest.approx(1040)
    assert new.approach_distances()[0] <= old.approach_distances()[0]


def test_access_and_egress_costs_count_toward_cutoff():
    net = build_access_network([feature("a", [(0, 0), (2400, 0)])], [[0, 140]], [[2400, 140]])
    assert net.approach_distances()[0] == pytest.approx(2680)
    assert not (net.approach_distances() <= 2500)[0]


def test_same_edge_origins_and_destinations_do_not_detour_via_endpoints():
    net = build_access_network([feature("a", [(0, 0), (1000, 0)])], [[400, 10]], [[600, 20]])
    assert net.approach_distances()[0] == pytest.approx(230)


def test_origins_and_other_destinations_are_not_transfer_shortcuts():
    lines = [feature("a", [(0, 0), (1000, 0)]), feature("b", [(0, 100), (1000, 100)])]
    net = build_access_network(lines, [[0, 0], [500, 50]], [[1000, 100], [500, 50]], access_max=60)
    # The midpoint residence and midpoint school see both roads, but cannot
    # connect them as through-nodes for the first origin's selected destination.
    distances = net.approach_distances([True, False])
    assert np.isinf(distances[0])
    assert np.isfinite(distances[1])


def test_oneway_and_reverse_direction_are_respected():
    for direction, origin, dest in ((1, [[100, 0]], [[0, 0]]), (-1, [[0, 0]], [[100, 0]])):
        net = build_access_network([feature("a", [(0, 0), (100, 0)], direction=direction)], origin, dest, access_max=0)
        assert np.isinf(net.approach_distances()[0])
    net = build_access_network([feature("a", [(0, 0), (100, 0)], direction=1)], [[0, 0]], [[100, 0]], access_max=0)
    assert net.approach_distances()[0] == 100


def test_same_level_t_junction_is_noded_but_bridge_crossing_is_not():
    ground = feature("a", [(0, 0), (100, 0)])
    branch = feature("b", [(50, 0), (50, 100)])
    net = build_access_network([ground, branch], [[0, 0]], [[50, 100]], access_max=0)
    assert net.approach_distances()[0] == 150
    bridge = feature("b", [(50, 0), (50, 100)], level="1", lateral_access=False)
    net = build_access_network([ground, bridge], [[0, 0]], [[50, 100]], access_max=0)
    assert np.isinf(net.approach_distances()[0])


def test_explicit_shared_osm_node_connects_bridge_to_surface_at_ramp():
    lines = [feature("a", [(0, 0), (50, 0)], node_refs=(1, 2)),
             feature("b", [(50, 0), (100, 0)], level="1", lateral_access=False, node_refs=(2, 3)),
             feature("c", [(100, 0), (150, 0)], node_refs=(3, 4))]
    net = build_access_network(lines, [[0, 0]], [[150, 0]], access_max=0)
    assert net.approach_distances()[0] == 150


def test_bridge_is_an_explicit_scenario_and_cannot_join_different_levels():
    lines = [feature("a", [(0, 0), (100, 0)]), feature("b", [(108, 0), (200, 0)])]
    net = build_access_network(lines, [[0, 0]], [[200, 0]], access_max=0)
    assert np.isinf(net.approach_distances()[0])
    bridges = net.bridge_links(10)
    assert len(bridges) == 1 and bridges[0][2] == 8
    assert net.approach_distances(graph=net.with_links(bridges))[0] == 200
    different_level = [lines[0], feature("b", [(108, 0), (200, 0)], level="1")]
    assert build_access_network(different_level, [], []).bridge_links(10) == []


def test_two_individually_useless_links_can_enable_a_route_together():
    lines = [feature("a", [(0, 0), (10, 0)]), feature("b", [(60, 0), (70, 0)]),
             feature("c", [(120, 0), (130, 0)])]
    net = build_access_network(lines, [[0, 0]], [[130, 0]], access_max=0)
    nodes = net.endpoint_indices([[10, 0], [60, 0], [70, 0], [120, 0]], .01)
    links = [(nodes[0], nodes[1], 50), (nodes[2], nodes[3], 50)]
    assert all(np.isinf(net.approach_distances(graph=net.with_links([link]))[0]) for link in links)
    assert net.approach_distances(graph=net.with_links(links))[0] == 130


def test_transition_partition_and_net_equal_gain_minus_loss():
    summary = transition_summary([True, False, True, False], [True, True, False, False], [1, 2, 3, 4])
    assert summary == dict(retained_pop=1, newly_reached_pop=2, lost_pop=3, still_unreached_pop=4, net_change_pop=-1)


def test_permissions_separate_facility_inventory_from_usable_routes():
    assert not bicycle_allowed({"highway": "cycleway", "bicycle": "no"})
    assert not bicycle_allowed({"highway": "cycleway", "access": "private"})
    assert bicycle_allowed({"highway": "cycleway", "access": "private", "bicycle": "yes"})
    assert not bicycle_allowed({"highway": "construction"})
    assert bicycle_direction({"oneway": "yes", "oneway:bicycle": "no"}) == 0
    assert bicycle_direction({"oneway": "yes", "cycleway": "opposite_lane"}) == 0
    assert bicycle_direction({"oneway": "-1"}) == -1


def test_empty_network_and_missing_destinations_are_explicitly_unreachable():
    net = build_access_network([], [[0, 0]], [[1, 0]])
    assert net.detached.tolist() == [True]
    assert np.isinf(net.approach_distances()[0])
    net = build_access_network([feature("a", [(0, 0), (1, 0)])], [[0, 0]], [])
    assert np.isinf(net.approach_distances()[0])


def test_source_order_does_not_change_access_cost():
    lines = [feature("a", [(0, 0), (1000, 0)]), feature("b", [(500, -100), (500, 100)])]
    first = build_access_network(lines, [[0, 5]], [[500, 100]], access_max=10)
    second = build_access_network(list(reversed(lines)), [[0, 5]], [[500, 100]], access_max=10)
    np.testing.assert_allclose(first.approach_distances(), second.approach_distances())
