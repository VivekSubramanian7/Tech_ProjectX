from app.services.ownership import OwnershipResolver


def test_known_path_prefix_resolves_owner():
    r = OwnershipResolver({"team-alpha/": "user-alpha"})
    result = r.resolve("/data/team-alpha/report.txt")
    assert result.owner_user_id == "user-alpha"
    assert result.resolution_method == "path_prefix"
    assert not result.unresolved


def test_unknown_path_is_unresolved_not_silent():
    r = OwnershipResolver()
    result = r.resolve("/unknown/file.txt")
    assert result.owner_user_id is None
    assert result.unresolved
    assert result.resolution_method == "unresolved"
