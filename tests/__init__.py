
def assertListEquals(test, expected):
    assert len(test) == len(expected)
    assert all([a == b for a, b in zip(test, expected)])
