import numpy as np
import pandas as pd
import pytest
from scipy.sparse.csgraph import dijkstra
from shapely.geometry import LineString

from analysis.access import (
    assign_districts,
    dest_node_distances,
    district_of,
    dong_district_map,
    popshare_reaching,
    reach_mask_from_distances,
    unsnapped_mask,
)
from analysis.network import bridge_components, build_graph, nearest_nodes

# Same topology as tests/test_network.py: a connected chain 0-1000-2000-3000
# plus a disconnected segment 5000-5500.
LINES = [
    LineString([(0, 0), (1000, 0)]),
    LineString([(1000, 0), (2000, 0)]),
    LineString([(2000, 0), (3000, 0)]),
    LineString([(5000, 0), (5500, 0)]),
]


def _toy_origins():
    # Origin 3 sits on the disconnected segment, so it can never reach the
    # destination on the main chain regardless of cutoff.
    return pd.DataFrame({
        "x": [0.0, 1000.0, 5000.0],
        "y": [5.0, 5.0, 5.0],
        "pop": [10.0, 20.0, 70.0],
    })


def _toy_dests():
    return pd.DataFrame({"x": [2000.0], "y": [0.0]})


def test_popshare_reaching_toy_graph():
    G, nodes = build_graph(LINES, snap=1.0)
    share, mask = popshare_reaching(G, nodes, _toy_origins(), _toy_dests(), cutoff=2500.0)
    assert share == 0.3
    assert mask.tolist() == [True, True, False]


def test_popshare_reaching_matches_brute_force_per_origin_dijkstra():
    """Equivalence check (brief Performance section): the multi-source
    dijkstra-from-destinations shortcut must agree with a brute-force
    per-origin dijkstra-to-every-destination on the same toy graph."""
    G, nodes = build_graph(LINES, snap=1.0)
    origins = _toy_origins()
    dests = _toy_dests()
    cutoff = 2500.0
    snap_max = 150.0

    _, mask = popshare_reaching(G, nodes, origins, dests, cutoff, snap_max=snap_max)

    o_idx = nearest_nodes(nodes, origins[["x", "y"]].to_numpy(), snap_max)
    d_idx = nearest_nodes(nodes, dests[["x", "y"]].to_numpy(), snap_max)
    d_idx = d_idx[d_idx >= 0]

    brute_mask = np.zeros(len(origins), dtype=bool)
    for i, node in enumerate(o_idx):
        if node < 0:
            continue
        dist = dijkstra(G, directed=False, indices=node, limit=cutoff)
        brute_mask[i] = bool(np.any(dist[d_idx] <= cutoff))

    assert mask.tolist() == brute_mask.tolist()


def test_popshare_reaching_empty_dests_returns_zero_share_all_false():
    G, nodes = build_graph(LINES, snap=1.0)
    origins = _toy_origins()
    dests = pd.DataFrame({"x": [], "y": []})
    share, mask = popshare_reaching(G, nodes, origins, dests, cutoff=2500.0)
    assert share == 0.0
    assert mask.tolist() == [False, False, False]


def test_popshare_reaching_origin_beyond_snap_max_excluded():
    G, nodes = build_graph(LINES, snap=1.0)
    origins = pd.DataFrame({"x": [0.0], "y": [200.0], "pop": [1.0]})
    dests = _toy_dests()
    share, mask = popshare_reaching(G, nodes, origins, dests, cutoff=2500.0, snap_max=150.0)
    assert share == 0.0
    assert mask.tolist() == [False]


def test_district_of_known_sgg_values():
    assert district_of("화성시 동탄구") == "dongtan"
    assert district_of("화성시 병점구") == "byeongjeom"
    assert district_of("화성시 효행구") == "hyohaeng"
    assert district_of("화성시 만세구") == "manse"


def test_district_of_unknown_returns_other():
    assert district_of("화성시 봉담읍") == "other"
    assert district_of("서울특별시 종로구") == "other"


def test_popshare_reaching_destination_beyond_snap_max_returns_zero_share_all_false():
    """M2: destination(s) present but every one is farther than snap_max from
    the network -- a distinct code path from an empty dests_df."""
    G, nodes = build_graph(LINES, snap=1.0)
    origins = _toy_origins()
    dests = pd.DataFrame({"x": [2000.0], "y": [200.0]})  # 200m off network > snap_max=150
    share, mask = popshare_reaching(G, nodes, origins, dests, cutoff=2500.0, snap_max=150.0)
    assert share == 0.0
    assert mask.tolist() == [False, False, False]


def test_popshare_reaching_multi_destination_matches_brute_force():
    """M1: two destinations at different points on the chain. Exercises that
    the multi-source min_only dijkstra picks whichever destination is nearer
    per origin -- including an origin reachable only via the farther-placed
    destination (x=3000) under the cutoff, not the nearer-placed one (x=0)."""
    G, nodes = build_graph(LINES, snap=1.0)
    origins = pd.DataFrame({
        "x": [1000.0, 2000.0, 5000.0],
        "y": [5.0, 5.0, 5.0],
        "pop": [10.0, 20.0, 70.0],
    })
    dests = pd.DataFrame({"x": [0.0, 3000.0], "y": [0.0, 0.0]})
    cutoff = 1000.0
    snap_max = 150.0

    share, mask = popshare_reaching(G, nodes, origins, dests, cutoff, snap_max=snap_max)
    # origin@1000 reaches only via the nearer dest@0 (dist 1000); origin@2000
    # reaches only via the farther-placed dest@3000 (dist 1000); origin@5000
    # is disconnected.
    assert mask.tolist() == [True, True, False]
    assert share == 0.3

    o_idx = nearest_nodes(nodes, origins[["x", "y"]].to_numpy(), snap_max)
    d_idx = nearest_nodes(nodes, dests[["x", "y"]].to_numpy(), snap_max)
    d_idx = d_idx[d_idx >= 0]

    brute_mask = np.zeros(len(origins), dtype=bool)
    for i, node in enumerate(o_idx):
        if node < 0:
            continue
        dist = dijkstra(G, directed=False, indices=node, limit=cutoff)
        brute_mask[i] = bool(np.any(dist[d_idx] <= cutoff))

    assert mask.tolist() == brute_mask.tolist()


def test_dest_node_distances_thresholding_matches_separate_popshare_reaching_runs():
    """M3: dest_node_distances computed once at the max cutoff, then
    thresholded per cutoff via reach_mask_from_distances, must match calling
    popshare_reaching separately (its own dijkstra) at each cutoff -- the
    equivalence scripts/04_access.py now relies on to run dijkstra once per
    (version, kind) instead of once per (version, kind, cutoff)."""
    G, nodes = build_graph(LINES, snap=1.0)
    origins = _toy_origins()
    dests = _toy_dests()
    cutoffs = [1000.0, 2000.0, 2500.0, 3000.0]
    max_cutoff = max(cutoffs)

    dist_from_dest = dest_node_distances(G, nodes, dests, limit=max_cutoff)

    for cutoff in cutoffs:
        expected_share, expected_mask = popshare_reaching(G, nodes, origins, dests, cutoff)
        share, mask = reach_mask_from_distances(nodes, origins, dist_from_dest, cutoff)
        assert mask.tolist() == expected_mask.tolist()
        assert share == expected_share


# --- I1 / M4: dong -> district join is a pure, tested function -------------

def _toy_pop_df():
    return pd.DataFrame({
        "시군구명": [
            "화성시 동탄구",  # aggregate row, empty 읍면동명 -> dropped (M4)
            "화성시 동탄구",
            "화성시 병점구",
            "화성시 효행구",
            "화성시 만세구",
            "서울특별시 종로구",  # out-of-scope sgg -> dropped entirely
        ],
        "읍면동명": [
            None,
            "동탄1동",
            "병점1동",
            "봉담읍",
            "우정읍",
            "청운효자동",
        ],
        "계": [500000, 49967, 36306, 112645, 16490, 10592],
    })


def test_dong_district_map_drops_empty_dong_and_non_hwaseong_rows():
    mapping = dong_district_map(_toy_pop_df())
    assert mapping == {
        "동탄1동": "dongtan",
        "병점1동": "byeongjeom",
        "봉담읍": "hyohaeng",
        "우정읍": "manse",
    }
    assert "청운효자동" not in mapping  # non-화성시 sgg, dropped by scope filter
    assert None not in mapping  # empty 읍면동명 aggregate row, dropped (M4)


def test_assign_districts_maps_known_dongs():
    mapping = dong_district_map(_toy_pop_df())
    assert assign_districts(["동탄1동", "병점1동", "동탄1동"], mapping) == [
        "dongtan", "byeongjeom", "dongtan",
    ]


def test_assign_districts_raises_on_unmatched_dong_with_name_in_message():
    mapping = dong_district_map(_toy_pop_df())
    with pytest.raises(ValueError, match="동탄99동"):
        assign_districts(["동탄1동", "동탄99동"], mapping)


# --- unsnapped_mask / detached vs attached-unreached (final-review I3) ----

def test_unsnapped_mask_flags_origin_beyond_snap_max():
    G, nodes = build_graph(LINES, snap=1.0)
    origins = pd.DataFrame({"x": [0.0, 0.0], "y": [5.0, 200.0], "pop": [10.0, 5.0]})
    mask = unsnapped_mask(nodes, origins, snap_max=150.0)
    assert mask.tolist() == [False, True]


def test_detached_plus_attached_unreached_plus_reaching_equals_total():
    # Toy graph (test_network.py topology): a connected chain 0-1000-2000-3000
    # plus a disconnected segment 5000-5500. All three toy origins sit ON the
    # network (within a few metres of a node) so none is "detached" here --
    # the disconnected-segment origin is "attached but unreached" (a
    # different code path from "detached", final-review I3's distinction).
    G, nodes = build_graph(LINES, snap=1.0)
    origins = _toy_origins()
    dests = _toy_dests()
    cutoff = 2500.0

    detached = unsnapped_mask(nodes, origins, snap_max=150.0)
    dist = dest_node_distances(G, nodes, dests, limit=cutoff)
    _, reaching = reach_mask_from_distances(nodes, origins, dist, cutoff)
    attached_unreached = (~detached) & (~reaching)

    pop = origins["pop"].to_numpy(dtype=float)
    total = pop.sum()
    pop_detached = pop[detached].sum()
    pop_attached_unreached = pop[attached_unreached].sum()
    pop_reaching = pop[reaching].sum()

    assert pop_detached == 0.0  # all three origins sit on some component
    assert pop_attached_unreached == 70.0  # the disconnected-segment origin
    assert pop_reaching == 30.0
    assert pop_detached + pop_attached_unreached + pop_reaching == total


# --- union superset monotonicity (final-review I6c) -----------------------

def test_union_bridged_reach_share_is_at_least_official_and_osm_alone():
    # An "official" line and an "osm" line whose facing ends are 8m apart
    # (within bridge tol=10m, Task 12c fix round 1) but far enough apart
    # that they are separate components at snap=1.0 unless bridged.
    official_lines = [LineString([(0, 0), (1000, 0)])]
    osm_lines = [LineString([(1008, 0), (2000, 0)])]

    dests = pd.DataFrame({"x": [1990.0], "y": [0.0]})
    origins = pd.DataFrame({
        "x": [0.0, 1990.0], "y": [0.0, 5.0], "pop": [50.0, 50.0],
    })
    cutoff = 2500.0

    G_off, nodes_off = build_graph(official_lines, snap=1.0)
    share_official, _ = popshare_reaching(G_off, nodes_off, origins, dests, cutoff)

    G_osm, nodes_osm = build_graph(osm_lines, snap=1.0)
    share_osm, _ = popshare_reaching(G_osm, nodes_osm, origins, dests, cutoff)

    G_union, nodes_union = build_graph(official_lines + osm_lines, snap=1.0)
    G_union, n_bridges, _ = bridge_components(G_union, nodes_union, tol=10.0)
    share_union, _ = popshare_reaching(G_union, nodes_union, origins, dests, cutoff)

    assert n_bridges == 1
    assert share_official == 0.0  # dest unsnappable on official-only graph
    assert share_osm == 0.5       # only the origin already on the osm line
    assert share_union == 1.0     # bridge lets the official-side origin reach too
    assert share_union >= share_osm >= share_official
