def test_probe_writes_into_the_repo():
    open("probe_dirty.txt", "w").write("x")
