from campus_unr_mcp.moodle_forms import extract_form_data


FORM = '''
<form action="modedit.php" method="post" id="mform1_abc" class="mform">
  <input type="hidden" name="course" value="503">
  <input type="hidden" name="sesskey" value="secret-session-key">
  <input type="text" name="name" value="Avisos 2026">
  <input type="checkbox" name="showdescription" value="1" checked>
  <input type="checkbox" name="completionusegrade" value="1">
  <textarea name="introeditor[text]"><p>Descripción</p></textarea>
  <select name="type"><option value="general" selected>Foro estándar</option><option value="news">Anuncios</option></select>
  <select name="visible"><option value="1" selected>Mostrar</option><option value="0">Ocultar</option></select>
  <input type="submit" name="submitbutton2" value="Guardar">
</form>
'''


def test_extract_form_data_preserves_successful_controls():
    action, data = extract_form_data(FORM)

    assert action == "modedit.php"
    assert data == [
        ("course", "503"),
        ("sesskey", "secret-session-key"),
        ("name", "Avisos 2026"),
        ("showdescription", "1"),
        ("introeditor[text]", "<p>Descripción</p>"),
        ("type", "general"),
        ("visible", "1"),
    ]


def test_extract_form_data_ignores_unchecked_and_submit_controls():
    _, data = extract_form_data(FORM)

    names = [name for name, _ in data]
    assert "completionusegrade" not in names
    assert "submitbutton2" not in names
