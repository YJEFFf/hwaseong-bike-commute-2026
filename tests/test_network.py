import numpy as np
from scipy.sparse.csgraph import dijkstra
from shapely.geometry import LineString

from analysis.network import bridge_components, build_graph, reach_weights

LINES = [LineString([(0, 0), (1000, 0)]), LineString([(1000, 0), (2000, 0)]),
         LineString([(2000, 0), (3000, 0)]), LineString([(5000, 0), (5500, 0)])]


def test_reach_within_cutoff_and_disconnected():
    G, nodes = build_graph(LINES, snap=1.0)
    origins = np.array([[0.0, 5.0]])
    dests = np.array([[2000.0, 0.0], [3000.0, 0.0], [5200.0, 0.0]])
    w = np.array([1.0, 10.0, 100.0])
    r = reach_weights(G, nodes, origins, dests, w, cutoff=2500.0)
    assert r.tolist() == [1.0]          # 2000m만 도달, 3000m 초과, 끊긴 망 제외


def test_origin_farther_than_snap_max_gets_reach_zero():
    G, nodes = build_graph(LINES, snap=1.0)
    # Origin is 200m off the network; default snap_max is 150.0, so it
    # cannot snap to any node and must contribute reach 0.
    origins = np.array([[0.0, 200.0]])
    dests = np.array([[2000.0, 0.0]])
    w = np.array([1.0])
    r = reach_weights(G, nodes, origins, dests, w, cutoff=2500.0, snap_max=150.0)
    assert r.tolist() == [0.0]


def test_duplicate_overlapping_segment_does_not_double_edge_weight():
    # Two identical LineStrings between the same pair of nodes (e.g. official
    # linework + OSM geometry overlapping) must NOT sum into a doubled edge
    # weight -- the true distance between the nodes is still 100.0, not 200.0.
    dup_lines = [LineString([(0, 0), (100, 0)]), LineString([(0, 0), (100, 0)])]
    G, nodes = build_graph(dup_lines, snap=1.0)

    i = np.where((nodes[:, 0] == 0) & (nodes[:, 1] == 0))[0][0]
    j = np.where((nodes[:, 0] == 100) & (nodes[:, 1] == 0))[0][0]
    assert G[i, j] == 100.0
    assert G[j, i] == 100.0

    # Also verify via reach_weights: with cutoff=150 the destination at
    # (100, 0) must be reachable, which would fail if the edge weight had
    # silently doubled to 200.0.
    origins = np.array([[0.0, 0.0]])
    dests = np.array([[100.0, 0.0]])
    w = np.array([1.0])
    r = reach_weights(G, nodes, origins, dests, w, cutoff=150.0, snap_max=10.0)
    assert r.tolist() == [1.0]


# --- bridge_components (Task 12c fix round 1) ---


def _node_index(nodes, x, y):
    return int(np.where((nodes[:, 0] == x) & (nodes[:, 1] == y))[0][0])


def test_bridge_components_connects_endpoints_within_tol():
    # Two disconnected chains with an 8m gap between (100,0) and (108,0).
    lines = [
        LineString([(0, 0), (100, 0)]),
        LineString([(108, 0), (200, 0)]),
    ]
    G, nodes = build_graph(lines, snap=1.0)

    G2, n_bridges, bridge_len_m = bridge_components(G, nodes, tol=10.0)

    assert n_bridges == 1
    assert bridge_len_m == 8.0

    i = _node_index(nodes, 100.0, 0.0)
    j = _node_index(nodes, 108.0, 0.0)
    assert G2[i, j] == 8.0
    assert G2[j, i] == 8.0


def test_bridge_components_no_bridge_when_gap_exceeds_tol():
    # Same layout but the gap (15m) exceeds tol (10m) -- no bridge.
    lines = [
        LineString([(0, 0), (100, 0)]),
        LineString([(115, 0), (200, 0)]),
    ]
    G, nodes = build_graph(lines, snap=1.0)

    G2, n_bridges, bridge_len_m = bridge_components(G, nodes, tol=10.0)

    assert n_bridges == 0
    assert bridge_len_m == 0.0
    assert (G2 != G).nnz == 0


def test_bridge_components_skips_dangling_node_near_same_component():
    # A single connected chain shaped like a near-closed loop: the two ends
    # ((0,0) and (5,5)) are only 7.07m apart but already belong to the SAME
    # connected component via the long way around -- must not bridge.
    lines = [
        LineString([(0, 0), (100, 0)]),
        LineString([(100, 0), (100, 100)]),
        LineString([(100, 100), (5, 100)]),
        LineString([(5, 100), (5, 5)]),
    ]
    G, nodes = build_graph(lines, snap=1.0)

    G2, n_bridges, bridge_len_m = bridge_components(G, nodes, tol=10.0)

    assert n_bridges == 0
    assert bridge_len_m == 0.0
    assert (G2 != G).nnz == 0


def test_bridge_components_makes_destination_reachable_only_via_bridge():
    lines = [
        LineString([(0, 0), (100, 0)]),
        LineString([(108, 0), (200, 0)]),
    ]
    G, nodes = build_graph(lines, snap=1.0)

    origin = _node_index(nodes, 0.0, 0.0)
    dest = _node_index(nodes, 200.0, 0.0)

    dist_before = dijkstra(G, directed=False, indices=origin)
    assert not np.isfinite(dist_before[dest])

    G2, n_bridges, _ = bridge_components(G, nodes, tol=10.0)
    assert n_bridges == 1

    dist_after = dijkstra(G2, directed=False, indices=origin)
    assert dist_after[dest] == 200.0  # 100 (seg1) + 8 (bridge) + 92 (seg2)
