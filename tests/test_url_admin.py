from types import SimpleNamespace

from campus_unr_mcp.client import CampusClient, CampusConfig


FORM = '''<form action="modedit.php" id="mform1_x"><input type="hidden" name="course" value="503"><input type="hidden" name="sesskey" value="abc"><input type="hidden" name="modulename" value="url"><input type="text" name="name" value="Introducción"><input type="url" name="externalurl" value="https://notion.so/anterior"><select name="visible"><option value="1" selected>Visible</option><option value="0">Oculto</option></select></form>'''


class FakeSession:
    def get(self, url, params):
        return SimpleNamespace(text=FORM, raise_for_status=lambda: None)
    def post(self, *args, **kwargs):
        raise AssertionError('dry-run no debe enviar un POST')
    def close(self):
        pass


def test_update_url_dry_run_validates_link_without_posting():
    client = CampusClient(CampusConfig(base_url="https://campus.example/"))
    client._web_login = lambda: FakeSession()

    result = client.update_url(
        94155,
        'https://drive.google.com/file/d/archivo/view?usp=sharing',
    )

    assert result == {
        'validated': True,
        'dry_run': True,
        'cmid': 94155,
        'external_url': 'https://drive.google.com/file/d/archivo/view?usp=sharing',
    }
