from switchboard.catalog import service_names
from switchboard.ownership import own, stale_entries


def test_every_catalog_service_resolves():
    for name in service_names():
        o = own(name)
        assert o is not None, name
        assert o.slack_channel.startswith("#")
        assert o.team


def test_unknown_service_is_none():
    assert own("does-not-exist") is None
    assert own(None) is None


def test_stale_codeowners_entry_is_flagged_not_hidden():
    o = own("notifications")
    assert o.stale is True
    assert o.source == "catalog"
    assert o.team == "client-apps"
    assert ("notifications", "growth") in stale_entries()


def test_fresh_entry_uses_codeowners():
    o = own("exports-scheduler")
    assert o.source == "codeowners"
    assert o.team == "data-platform"
    assert o.stale is False
