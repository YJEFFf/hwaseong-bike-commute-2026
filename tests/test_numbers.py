from analysis.numbers import record, read_numbers


def test_record_upserts_and_read_numbers_reflects_overwrite(tmp_path):
    path = tmp_path / "numbers.csv"

    record("a", 1, "first", path=path)
    record("b", 2, "second", path=path)
    record("a", 99, "updated", path=path)

    numbers = read_numbers(path=path)

    assert len(numbers) == 2
    assert numbers["a"] == "99"
    assert numbers["b"] == "2"
