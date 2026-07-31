from dash_bucket_upload._keys import (
    DEFAULT_MIN_PART,
    MAX_PART,
    MiB,
    TARGET_MAX_PARTS,
    compute_part_size,
    generate_key,
    key_matches,
)


def test_part_size_small_file():
    assert compute_part_size(1 * MiB) == DEFAULT_MIN_PART
    assert compute_part_size(0) == DEFAULT_MIN_PART


def test_part_size_stays_under_part_cap():
    for size in (5 * 1024**3, 200 * 1024**3, 5 * 1024**4):
        part = compute_part_size(size)
        assert size / part <= TARGET_MAX_PARTS
        assert part % MiB == 0
        assert DEFAULT_MIN_PART <= part <= MAX_PART


def test_part_size_override():
    assert compute_part_size(10 * 1024**3, override = 32 * MiB) == 32 * MiB


def test_generate_key_shape():
    key = generate_key('incoming', 'data file.csv')
    assert key.startswith('incoming/')
    assert key.endswith('/data file.csv')
    assert key_matches('incoming', key)


def test_generate_key_empty_prefix():
    key = generate_key('', 'a.bin')
    assert key_matches('', key)
    assert key.count('/') == 1


def test_generate_keys_never_collide():
    keys = {generate_key('p', 'same-name.txt') for _ in range(50)}
    assert len(keys) == 50


def test_key_matches_rejects_foreign_keys():
    assert not key_matches('incoming', 'other/6f6b2c2e-3f6e-4d0a-9d5c-1c2b3a4d5e6f/x.txt')
    assert not key_matches('incoming', 'incoming/not-a-uuid/x.txt')
    assert not key_matches('incoming', 'incoming/6f6b2c2e-3f6e-4d0a-9d5c-1c2b3a4d5e6f/a/b.txt')
    assert not key_matches('incoming', 'incoming/6f6b2c2e-3f6e-4d0a-9d5c-1c2b3a4d5e6f/')
