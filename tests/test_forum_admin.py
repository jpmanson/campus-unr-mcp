from types import SimpleNamespace

from campus_unr_mcp.client import CampusClient, CampusConfig


FORM = '''<form action="modedit.php" id="mform1_x"><input type="hidden" name="course" value="503"><input type="hidden" name="sesskey" value="abc"><input type="text" name="name" value="Antes"><select name="visible"><option value="1" selected>Visible</option><option value="0">Oculto</option></select></form>'''


class FakeSession:
    def __init__(self):
        self.posts = []
    def get(self, url, params):
        return SimpleNamespace(text=FORM, raise_for_status=lambda: None)
    def post(self, *args, **kwargs):
        self.posts.append((args, kwargs))
        return SimpleNamespace(url="https://campus.example/course/view.php?id=503", raise_for_status=lambda: None)
    def close(self):
        pass


def test_update_forum_dry_run_returns_normalized_change_without_posting():
    client = CampusClient(CampusConfig(base_url="https://campus.example/"))
    session = FakeSession()
    client._web_login = lambda: session

    result = client.update_forum(121831, "Avisos 2026 C1", visible=False)

    assert result == {
        "validated": True,
        "dry_run": True,
        "cmid": 121831,
        "name": "Avisos 2026 C1",
        "visible": False,
    }
    assert session.posts == []
