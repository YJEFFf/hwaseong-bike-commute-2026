import numpy as np
import rasterio
from affine import Affine
from pyproj import Transformer
from shapely.geometry import box

from analysis.population import dasymetric_points, load_dong_population


def test_load_dong_population_filters_and_types(tmp_path):
    csv_path = tmp_path / "pop.csv"
    header = ["행정기관코드", "기준연월", "시도명", "시군구명", "읍면동명", "계", "남자", "여자"]
    rows = [
        ["4159125000", "2026-08-31", "경기도", "화성시 만세구", "우정읍", "16490", "8000", "8490"],
        # aggregate row: 시군구명 화성시-prefixed but 읍면동명 empty -> must be dropped
        ["4159100000", "2026-08-31", "경기도", "화성시", "", "500000", "250000", "250000"],
        # non-화성 row -> must be dropped
        ["1111051500", "2026-08-31", "서울특별시", "종로구", "청운효자동", "10592", "4806", "5786"],
    ]
    lines = [",".join(header)] + [",".join(r) for r in rows]
    csv_path.write_bytes("\n".join(lines).encode("cp949"))

    df = load_dong_population(csv_path, sgg_prefix="화성시")

    assert list(df.columns) == ["code", "sgg", "dong", "total"]
    assert len(df) == 1
    row = df.iloc[0]
    assert row["dong"] == "우정읍"
    assert row["sgg"] == "화성시 만세구"
    assert int(row["total"]) == 16490


def _write_ghsl_tif(path, arr, transform, nodata=-200.0):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=arr.shape[0],
        width=arr.shape[1],
        count=1,
        dtype="float64",
        crs="ESRI:54009",
        transform=transform,
        nodata=nodata,
    ) as ds:
        ds.write(arr, 1)


def _synthetic_raster(tmp_path):
    """4x8 grid of 100m cells in ESRI:54009, near lon 127.0 / lat 37.2.

    The grid is split by ROW (not column): top 2 rows (0-1, all 8 cols) =
    dong A, bottom 2 rows (2-3, all 8 cols) = dong B. A row-based split is
    used deliberately: reprojecting Mollweide's axis-aligned grid to a local
    TM CRS (EPSG:5186) shears it noticeably at this longitude (row-to-row x
    drift is a large fraction of a 100m cell, since Mollweide's vertical grid
    lines are not meridians away from its central meridian), so a
    column-based split would leave the two blocks' reprojected footprints
    overlapping in x. Splitting by row keeps the y-extents of A and B safely
    separated regardless of that shear.

    Dong A carries two non-zero cells, 6 and 4 (sum 10); dong B is all 0.
    """
    to_moll = Transformer.from_crs(4326, "ESRI:54009", always_xy=True)
    x0, y0 = to_moll.transform(127.0, 37.2)

    transform = Affine(100.0, 0.0, x0, 0.0, -100.0, y0)
    arr = np.zeros((4, 8), dtype="float64")
    arr[0, 0] = 6.0
    arr[1, 5] = 4.0
    # rows 2-3 (dong B) stay all zero

    raster_path = tmp_path / "ghsl.tif"
    _write_ghsl_tif(raster_path, arr, transform)

    from_moll = Transformer.from_crs("ESRI:54009", 5186, always_xy=True)

    def block_polygon(row0, row1):
        xs, ys = [], []
        for row in range(row0, row1):
            for col in range(8):
                cx = x0 + (col + 0.5) * 100.0
                cy = y0 - (row + 0.5) * 100.0
                px, py = from_moll.transform(cx, cy)
                xs.append(px)
                ys.append(py)
        pad = 5.0
        return box(min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)

    dong_polys = {
        "A": block_polygon(0, 2),
        "B": block_polygon(2, 4),
    }
    return raster_path, dong_polys


def test_dasymetric_points_scales_to_dong_totals(tmp_path):
    raster_path, dong_polys = _synthetic_raster(tmp_path)
    dong_totals = {"A": 100, "B": 40}

    df = dasymetric_points(raster_path, dong_polys, dong_totals)

    assert list(df.columns) == ["x", "y", "pop", "dong"]
    assert (df["pop"] > 0).all()

    a_rows = df[df["dong"] == "A"]
    b_rows = df[df["dong"] == "B"]

    # dong A: raster sum was 10 > 0, so only the 2 nonzero cells (6 and 4)
    # survive the pop > 0 filter, scaled proportionally to 60 and 40.
    assert len(a_rows) == 2
    assert np.isclose(a_rows["pop"].sum(), 100, rtol=1e-6)
    assert np.allclose(sorted(a_rows["pop"]), [40.0, 60.0])

    # dong B: raster sum was 0, so its total is spread uniformly over all
    # 16 cells whose centers fall inside it.
    assert len(b_rows) == 16
    assert np.isclose(b_rows["pop"].sum(), 40, rtol=1e-6)
    assert np.allclose(b_rows["pop"], 40 / 16)


def test_dasymetric_points_skips_tile_that_does_not_overlap_dongs(tmp_path):
    """Regression for the WindowError found during the real-data run: when a
    GHSL tile's extent doesn't overlap the dong polygons at all (e.g. two
    tiles are supplied but the target city sits entirely inside just one of
    them), `_cells_in_window` must return an empty result for that tile
    instead of raising, and the final totals must be unaffected."""
    raster_path, dong_polys = _synthetic_raster(tmp_path)

    # A second tile far away (500 km east in Mollweide space) that cannot
    # possibly overlap the dong polygons' (padded) bounding box.
    to_moll = Transformer.from_crs(4326, "ESRI:54009", always_xy=True)
    fx0, fy0 = to_moll.transform(127.0, 37.2)
    fx0 += 500_000.0
    far_transform = Affine(100.0, 0.0, fx0, 0.0, -100.0, fy0)
    far_arr = np.full((4, 8), 99.0, dtype="float64")
    far_path = tmp_path / "ghsl_far.tif"
    _write_ghsl_tif(far_path, far_arr, far_transform)

    dong_totals = {"A": 100, "B": 40}

    # decoy tile listed first, so a bug that raises on the very first
    # non-overlapping tile would still be caught.
    df = dasymetric_points([far_path, raster_path], dong_polys, dong_totals)

    assert list(df.columns) == ["x", "y", "pop", "dong"]
    a_rows = df[df["dong"] == "A"]
    b_rows = df[df["dong"] == "B"]
    assert len(a_rows) == 2
    assert np.isclose(a_rows["pop"].sum(), 100, rtol=1e-6)
    assert len(b_rows) == 16
    assert np.isclose(b_rows["pop"].sum(), 40, rtol=1e-6)


def test_dasymetric_points_handles_seam_between_adjacent_tiles(tmp_path):
    """Two adjacent (edge-sharing, non-overlapping) GHSL tiles together cover
    one dong that straddles the seam between them. Cells must not be double
    counted (no duplicate (x, y) across the two tiles) and the dong's total
    must still be distributed exactly, split across both tiles' cells."""
    to_moll = Transformer.from_crs(4326, "ESRI:54009", always_xy=True)
    x0, y0 = to_moll.transform(127.0, 37.2)

    # Tile 1: cols 0-3 (local), rows 0-1. Tile 2: cols 4-7 (global), rows 0-1,
    # starting exactly where tile 1's extent ends -- a shared seam, not an
    # overlap.
    transform1 = Affine(100.0, 0.0, x0, 0.0, -100.0, y0)
    arr1 = np.zeros((2, 4), dtype="float64")
    arr1[0, 0] = 6.0  # global (row0, col0)
    path1 = tmp_path / "ghsl_tile1.tif"
    _write_ghsl_tif(path1, arr1, transform1)

    transform2 = Affine(100.0, 0.0, x0 + 4 * 100.0, 0.0, -100.0, y0)
    arr2 = np.zeros((2, 4), dtype="float64")
    arr2[1, 1] = 4.0  # global (row1, col5)
    path2 = tmp_path / "ghsl_tile2.tif"
    _write_ghsl_tif(path2, arr2, transform2)

    from_moll = Transformer.from_crs("ESRI:54009", 5186, always_xy=True)

    xs, ys = [], []
    for row in range(2):
        for col in range(8):
            cx = x0 + (col + 0.5) * 100.0
            cy = y0 - (row + 0.5) * 100.0
            px, py = from_moll.transform(cx, cy)
            xs.append(px)
            ys.append(py)
    pad = 5.0
    dong_poly = box(min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)

    dong_totals = {"C": 100}
    df = dasymetric_points([path1, path2], {"C": dong_poly}, dong_totals)

    assert len(df) == 2
    assert np.isclose(df["pop"].sum(), 100, rtol=1e-6)
    assert np.allclose(sorted(df["pop"]), [40.0, 60.0])

    coords = list(zip(df["x"].round(6), df["y"].round(6)))
    assert len(coords) == len(set(coords))  # no cell counted by both tiles
