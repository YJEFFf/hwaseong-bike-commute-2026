import numpy as np
import pandas as pd
from scipy.sparse.csgraph import dijkstra
from shapely.geometry import LineString, box

from analysis.access import dest_node_distances
from analysis.candidates import (
    bottom_share_mask,
    dangling_candidates,
    distinct_reach_pop,
    link_benefit,
    stable_origin_rank,
    tie_inclusive_topn,
)
from analysis.network import build_graph, nearest_nodes

REGION = {"R1": box(-50, -50, 400, 650)}


# --- dangling_candidates -----------------------------------------------

def test_dangling_candidates_different_components_within_max_gap():
    # Two collinear lines with a 40m gap between (100,0) and (140,0),
    # otherwise unconnected -> exactly one candidate.
    lines = [
        LineString([(0, 0), (100, 0)]),
        LineString([(140, 0), (240, 0)]),
    ]
    G, nodes = build_graph(lines, snap=1.0)

    cands = dangling_candidates(G, nodes, REGION, max_gap=100.0)

    assert len(cands) == 1
    row = cands.iloc[0]
    assert row["region"] == "R1"
    assert row["gap_m"] == 40.0
    endpoints = {(row["x1"], row["y1"]), (row["x2"], row["y2"])}
    assert endpoints == {(100.0, 0.0), (140.0, 0.0)}


def test_dangling_candidates_same_component_but_long_detour_still_candidate():
    # Same two dangling ends (100,0)/(140,0), but now joined into a single
    # connected component via a long detour through (0,600)-(240,600) that
    # does NOT touch (100,0)/(140,0) themselves, so they stay degree-1.
    # Network distance via the detour is 1640m >> max(3*40, 40+200)=240m.
    lines = [
        LineString([(0, 0), (100, 0)]),
        LineString([(140, 0), (240, 0)]),
        LineString([(0, 0), (0, 600)]),
        LineString([(0, 600), (240, 600)]),
        LineString([(240, 600), (240, 0)]),
    ]
    G, nodes = build_graph(lines, snap=1.0)

    cands = dangling_candidates(G, nodes, REGION, max_gap=100.0)

    pair = cands[(cands.gap_m == 40.0)]
    assert len(pair) == 1


def test_dangling_candidates_none_when_gap_exceeds_max_gap():
    # Two lines 150m apart -> no candidate at max_gap=100.
    lines = [
        LineString([(0, 0), (100, 0)]),
        LineString([(250, 0), (350, 0)]),
    ]
    G, nodes = build_graph(lines, snap=1.0)

    cands = dangling_candidates(G, nodes, REGION, max_gap=100.0)

    assert len(cands) == 0


def test_dangling_candidates_ids_are_stable_row_positions():
    lines = [
        LineString([(0, 0), (100, 0)]),
        LineString([(140, 0), (240, 0)]),
    ]
    G, nodes = build_graph(lines, snap=1.0)
    cands = dangling_candidates(G, nodes, REGION, max_gap=100.0)
    assert cands["cand_id"].tolist() == list(range(len(cands)))
    assert list(cands.columns) == ["cand_id", "region", "gap_m", "x1", "y1", "x2", "y2"]


# --- link_benefit --------------------------------------------------------

# Destination at (990,0) is a vertex on the main chain (0,0)-(990,0)-(1000,0).
# A disconnected piece (1030,0)-(1200,0) sits 30m away from the chain's other
# dangling end (1000,0). Candidate link u=(1000,0), v=(1030,0), L=30.
LINK_LINES = [
    LineString([(0, 0), (990, 0), (1000, 0)]),
    LineString([(1030, 0), (1200, 0)]),
]


def _link_benefit_setup(cutoff):
    G, nodes = build_graph(LINK_LINES, snap=1.0)
    dests = pd.DataFrame({"x": [990.0], "y": [0.0]})
    origins = pd.DataFrame({"x": [1030.0], "y": [0.0], "pop": [100.0]})

    d0 = dest_node_distances(G, nodes, dests, limit=cutoff)

    u = int(np.where((nodes[:, 0] == 1000.0) & (nodes[:, 1] == 0.0))[0][0])
    v = int(np.where((nodes[:, 0] == 1030.0) & (nodes[:, 1] == 0.0))[0][0])
    L = float(np.hypot(nodes[v, 0] - nodes[u, 0], nodes[v, 1] - nodes[u, 1]))
    assert L == 30.0

    du = dijkstra(G, directed=False, indices=u, limit=cutoff)
    dv = dijkstra(G, directed=False, indices=v, limit=cutoff)

    origin_nodes = nearest_nodes(nodes, origins[["x", "y"]].to_numpy(), 150.0)

    return G, nodes, d0, du, dv, u, v, L, origin_nodes, origins


def test_link_benefit_disconnected_origin_newly_reaches_within_cutoff():
    cutoff = 500.0
    G, nodes, d0, du, dv, u, v, L, origin_nodes, origins = _link_benefit_setup(cutoff)

    mask = link_benefit(d0, du, dv, L, d0[u], d0[v], origin_nodes, cutoff)

    assert mask.tolist() == [True]


def test_link_benefit_matches_brute_force_rebuild_and_dijkstra():
    cutoff = 500.0
    G, nodes, d0, du, dv, u, v, L, origin_nodes, origins = _link_benefit_setup(cutoff)
    mask = link_benefit(d0, du, dv, L, d0[u], d0[v], origin_nodes, cutoff)

    # Brute force: rebuild the graph with the new straight link added, then
    # dijkstra from the destination and compare reach directly.
    brute_lines = LINK_LINES + [LineString([(1000.0, 0.0), (1030.0, 0.0)])]
    G2, nodes2 = build_graph(brute_lines, snap=1.0)
    dests_xy = np.array([[990.0, 0.0]])
    d_idx = nearest_nodes(nodes2, dests_xy, 150.0)
    dist_all = dijkstra(G2, directed=False, indices=d_idx, limit=cutoff, min_only=True)

    origin_xy = origins[["x", "y"]].to_numpy()
    o_idx = nearest_nodes(nodes2, origin_xy, 150.0)
    brute_reaches = dist_all[o_idx] <= cutoff
    # Baseline (no link) never reaches, so brute-force reach == newly-reach.
    assert mask.tolist() == brute_reaches.tolist()


def test_link_benefit_node_exactly_at_cutoff_counts_as_reaching():
    # d1[v] = dv[v](0) + L(30) + d0[u](10) = 40 exactly -> cutoff=40 must
    # still count as reaching (inclusive <=).
    cutoff = 40.0
    G, nodes, d0, du, dv, u, v, L, origin_nodes, origins = _link_benefit_setup(cutoff)

    mask = link_benefit(d0, du, dv, L, d0[u], d0[v], origin_nodes, cutoff)

    assert mask.tolist() == [True]


def test_link_benefit_does_not_mark_already_reaching_origin():
    # With a very large cutoff the origin already reaches via d0 alone once
    # cutoff exceeds its full detour distance is irrelevant here -- instead
    # directly check that an origin already within cutoff via d0 is not
    # counted again as "newly" reaching.
    cutoff = 500.0
    G, nodes, d0, du, dv, u, v, L, origin_nodes, origins = _link_benefit_setup(cutoff)
    # Force d0 at the origin's node to already be within cutoff.
    d0_already = d0.copy()
    d0_already[v] = 5.0

    mask = link_benefit(d0_already, du, dv, L, d0[u], d0_already[v], origin_nodes, cutoff)

    assert mask.tolist() == [False]


# --- bottom_share_mask ----------------------------------------------------

def test_bottom_share_mask_cumulates_by_population_from_largest_distance():
    pop = [10, 10, 10, 70]
    dist = [np.inf, 900, 100, 50]

    mask = bottom_share_mask(dist, pop, share=0.2)

    assert mask.tolist() == [True, True, False, False]


def test_bottom_share_mask_all_false_when_total_pop_zero():
    mask = bottom_share_mask([np.inf, 10.0], [0.0, 0.0], share=0.2)
    assert mask.tolist() == [False, False]


# --- bottom_share_mask tie-break / permutation invariance (final-review C1) -

def test_bottom_share_mask_ties_on_d0_broken_by_tiebreak_desc():
    # Two origins tie on d0 (both inf); tiebreak_desc (euclidean distance to
    # nearest school) must break the tie -- larger euclid distance = worse
    # served = picked first into the bottom share.
    pop = [50.0, 50.0]
    d0 = [np.inf, np.inf]
    euclid = [100.0, 900.0]  # origin 1 is farther from school -> worse served

    mask = bottom_share_mask(d0, pop, share=0.2, tiebreak_desc=euclid)

    # target = 0.2*100 = 20; origin 1 (euclid=900) must be picked first and
    # alone covers pop=50 >= 20, so only origin 1 is marked.
    assert mask.tolist() == [False, True]


def test_bottom_share_mask_row_permutation_invariant_via_stable_id():
    # Same data, two different row orders (with a matching stable_id per
    # row carried along) -- the SET of stable_ids marked must be identical.
    pop_a = np.array([10.0, 10.0, 10.0, 70.0])
    d0_a = np.array([np.inf, 900.0, 100.0, 50.0])
    euclid_a = np.array([500.0, 400.0, 300.0, 200.0])
    sid_a = np.array([0, 1, 2, 3])

    perm = [2, 0, 3, 1]
    pop_b, d0_b, euclid_b, sid_b = pop_a[perm], d0_a[perm], euclid_a[perm], sid_a[perm]

    mask_a = bottom_share_mask(d0_a, pop_a, share=0.2, tiebreak_desc=euclid_a, stable_id=sid_a)
    mask_b = bottom_share_mask(d0_b, pop_b, share=0.2, tiebreak_desc=euclid_b, stable_id=sid_b)

    marked_ids_a = set(sid_a[mask_a].tolist())
    marked_ids_b = set(sid_b[mask_b].tolist())
    assert marked_ids_a == marked_ids_b == {0, 1}


def test_bottom_share_mask_without_tiebreak_args_matches_previous_behaviour():
    # Default args (no tiebreak_desc/stable_id) must reproduce the exact
    # pre-C1 behaviour (stable sort on d0 alone, ties by array position).
    pop = [10, 10, 10, 70]
    dist = [np.inf, 900, 100, 50]
    assert bottom_share_mask(dist, pop, share=0.2).tolist() == [True, True, False, False]


# --- stable_origin_rank (final-review C1) ---------------------------------

def test_stable_origin_rank_invariant_under_row_permutation():
    xy = np.array([[0.0, 0.0], [5.0, 5.0], [1.0, 9.0], [3.0, 2.0]])
    perm = [2, 0, 3, 1]

    rank_a = stable_origin_rank(xy)
    rank_b = stable_origin_rank(xy[perm])

    # rank of row i in the original == rank of the same coordinate wherever
    # it lands in the permuted array.
    for orig_i, perm_i in enumerate(perm):
        assert rank_a[perm_i] == rank_b[orig_i]


# --- distinct_reach_pop (final-review C2) ---------------------------------

def test_distinct_reach_pop_counts_shared_origin_once():
    pop = np.array([10.0, 20.0, 30.0])
    region_mask = np.array([True, True, True])
    # Both links reach origin 0 and 1; link "b" also reaches origin 2.
    masks = {
        "a": np.array([True, True, False]),
        "b": np.array([True, True, True]),
    }
    # Sum would double-count origins 0,1: 10+20 (a) + 10+20+30 (b) = 90.
    assert distinct_reach_pop(["a", "b"], masks, pop, region_mask) == 60.0


def test_distinct_reach_pop_ignores_unavailable_candidates():
    pop = np.array([10.0, 20.0])
    region_mask = np.array([True, True])
    masks = {"a": np.array([True, False]), "b": None}
    assert distinct_reach_pop(["a", "b"], masks, pop, region_mask) == 10.0


def test_distinct_reach_pop_applies_extra_mask():
    pop = np.array([10.0, 20.0, 30.0])
    region_mask = np.array([True, True, True])
    masks = {"a": np.array([True, True, True])}
    extra = np.array([False, True, False])
    assert distinct_reach_pop(["a"], masks, pop, region_mask, extra_mask=extra) == 20.0


# --- tie_inclusive_topn (final-review I5) ---------------------------------

def test_tie_inclusive_topn_includes_all_ties_at_boundary():
    # 5 candidates, scores such that positions 3,4,5 (n=3) all tie at 10.
    scores = {1: 50, 2: 30, 3: 10, 4: 10, 5: 10}
    selected, size = tie_inclusive_topn(scores.keys(), lambda c: scores[c], n=3)
    assert set(selected) == {1, 2, 3, 4, 5}
    assert size == 5


def test_tie_inclusive_topn_no_ties_returns_exactly_n():
    scores = {1: 50, 2: 40, 3: 30, 4: 20, 5: 10}
    selected, size = tie_inclusive_topn(scores.keys(), lambda c: scores[c], n=3)
    assert selected == [1, 2, 3]
    assert size == 3


def test_tie_inclusive_topn_ascending_for_short_rule():
    gaps = {1: 5.0, 2: 3.0, 3: 3.0, 4: 8.0}
    selected, size = tie_inclusive_topn(gaps.keys(), lambda c: gaps[c], n=1, ascending=True)
    assert set(selected) == {2, 3}
    assert size == 2


def test_tie_inclusive_topn_display_order_by_gap_then_cand_id():
    gaps = {5: 10.0, 3: 20.0, 1: 10.0}
    selected, _ = tie_inclusive_topn(gaps.keys(), lambda c: -gaps[c], n=3, gap_of=lambda c: gaps[c])
    assert selected == [1, 5, 3]  # gap 10 (ids 1,5 asc) before gap 20 (id 3)


def test_tie_inclusive_topn_fewer_candidates_than_n_returns_all():
    scores = {1: 5, 2: 3}
    selected, size = tie_inclusive_topn(scores.keys(), lambda c: scores[c], n=20)
    assert set(selected) == {1, 2}
    assert size == 2
