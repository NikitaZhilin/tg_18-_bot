from __future__ import annotations

from zipfile import ZipFile

from app.services.admin_service import AdminService
from app.services.export_service import EXPORT_COLUMNS, save_cards_xlsx
from tests.helpers import import_seed, migrated_db


def test_cards_export_is_excel_readable_with_cyrillic_text(tmp_path):
    db = migrated_db(tmp_path)
    import_seed(db)
    rows = AdminService(db).export_rows()
    path = tmp_path / "cards_export.xlsx"

    save_cards_xlsx(rows, path)

    with ZipFile(path) as archive:
        names = set(archive.namelist())
        sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "xl/workbook.xml" in names
    assert "xl/worksheets/sheet1.xml" in names
    assert f'A1" t="inlineStr"' in sheet_xml
    assert f"{chr(64 + len(EXPORT_COLUMNS))}1" in sheet_xml
    assert "<t>id</t>" in sheet_xml
    assert "<t>text</t>" in sheet_xml
    assert "Сделайте" in sheet_xml
    assert 'state="frozen"' in sheet_xml
    db.close()
