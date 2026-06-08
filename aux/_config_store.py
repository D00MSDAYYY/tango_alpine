import json
import re
import zipfile
from pathlib import Path
from typing import Any, Protocol
from xml.etree import ElementTree as ET


class ConfigStore(Protocol):
    def load(self, path: str | Path) -> dict[str, Any]:
        ...

    def save(self, path: str | Path, data: dict[str, Any]) -> None:
        ...


class JsonConfigStore:
    def load(self, path: str | Path) -> dict[str, Any]:
        with open(path, encoding="utf-8") as file:
            return json.load(file)

    def save(self, path: str | Path, data: dict[str, Any]) -> None:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)


class XlsxConfigStore:
    SETTINGS_SHEET = "settings"
    INDEX_SHEET = "index"
    INDEX_COLUMNS = ("name", "type")
    SETTINGS_COLUMNS = ("key", "value")
    COMMON_CHANNEL_COLUMNS = (
        "name",
        "units",
        "line_color",
        "line_width",
        "show_dots",
    )

    def load(self, path: str | Path) -> dict[str, Any]:
        tables = _read_xlsx_tables(Path(path))
        index = self._require_sheet(tables, self.INDEX_SHEET)

        config: dict[str, Any] = self._read_settings(tables)
        config["cnls_setts"] = self._read_channels(tables, index)
        return config

    def save(self, path: str | Path, data: dict[str, Any]) -> None:
        tables: dict[str, list[list[Any]]] = {}
        tables[self.SETTINGS_SHEET] = self._settings_table(data)
        tables[self.INDEX_SHEET] = self._index_table(data)

        rows_by_type: dict[str, list[dict[str, Any]]] = {}
        for channel in data.get("cnls_setts", []):
            channel_type = channel.get("type")
            if not channel_type:
                raise ValueError("Channel without 'type' cannot be written to XLSX")
            rows_by_type.setdefault(channel_type, []).append(channel)

        for channel_type, channels in rows_by_type.items():
            tables[channel_type] = self._channel_table(channels)

        _write_xlsx_tables(Path(path), tables)

    def _read_settings(self, tables: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        settings = {}
        for row in tables.get(self.SETTINGS_SHEET, []):
            key = row.get("key")
            if key:
                settings[str(key)] = row.get("value")
        return settings

    def _read_channels(
        self,
        tables: dict[str, list[dict[str, Any]]],
        index: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        channels = []
        rows_by_type = {
            sheet_name: self._rows_by_name(rows)
            for sheet_name, rows in tables.items()
            if sheet_name not in (self.SETTINGS_SHEET, self.INDEX_SHEET)
        }

        for item in index:
            name = item.get("name")
            channel_type = item.get("type")
            if not name or not channel_type:
                raise ValueError("Every row in 'index' must contain 'name' and 'type'")

            type_rows = rows_by_type.get(str(channel_type))
            if type_rows is None:
                raise ValueError(f"Sheet '{channel_type}' is required for channel '{name}'")

            row = type_rows.get(str(name))
            if row is None:
                raise ValueError(
                    f"Sheet '{channel_type}' does not contain settings for channel '{name}'"
                )
            channels.append(self._channel_from_row(str(channel_type), str(name), row))
        return channels

    def _channel_from_row(
        self,
        channel_type: str,
        name: str,
        row: dict[str, Any],
    ) -> dict[str, Any]:
        line_color = row.get("line_color")
        line_width = row.get("line_width")
        show_dots = row.get("show_dots")
        channel = {
            "type": channel_type,
            "name": name,
            "units": row.get("units"),
            "appearence": {},
            "setup_config": {},
        }
        if line_color not in (None, ""):
            channel["appearence"]["line_color"] = line_color
        if line_width not in (None, ""):
            channel["appearence"]["line_width"] = line_width
        if show_dots not in (None, ""):
            channel["appearence"]["show_dots"] = show_dots

        for key, value in row.items():
            if key in self.COMMON_CHANNEL_COLUMNS or value in (None, ""):
                continue
            channel["setup_config"][key] = value
        return channel

    def _settings_table(self, data: dict[str, Any]) -> list[list[Any]]:
        rows = [list(self.SETTINGS_COLUMNS)]
        for key in (
            "time_range",
            "history_range",
            "max_redraw_hz",
            "max_plot_points",
            "x_axis_label",
            "y_axis_label",
        ):
            rows.append([key, data.get(key)])
        return rows

    def _index_table(self, data: dict[str, Any]) -> list[list[Any]]:
        rows = [list(self.INDEX_COLUMNS)]
        for channel in data.get("cnls_setts", []):
            rows.append([channel.get("name"), channel.get("type")])
        return rows

    def _channel_table(self, channels: list[dict[str, Any]]) -> list[list[Any]]:
        setup_columns = []
        for channel in channels:
            for key in channel.get("setup_config", {}):
                if key not in setup_columns:
                    setup_columns.append(key)

        columns = list(self.COMMON_CHANNEL_COLUMNS) + setup_columns
        rows = [columns]
        for channel in channels:
            appearence = channel.get("appearence", {})
            setup_config = channel.get("setup_config", {})
            row = [
                channel.get("name"),
                channel.get("units"),
                appearence.get("line_color"),
                appearence.get("line_width"),
                appearence.get("show_dots"),
            ]
            row.extend(setup_config.get(column) for column in setup_columns)
            rows.append(row)
        return rows

    def _require_sheet(
        self,
        tables: dict[str, list[dict[str, Any]]],
        sheet_name: str,
    ) -> list[dict[str, Any]]:
        sheet = tables.get(sheet_name)
        if sheet is None:
            raise ValueError(f"XLSX config must contain sheet '{sheet_name}'")
        return sheet

    def _rows_by_name(self, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        result = {}
        for row in rows:
            name = row.get("name")
            if not name:
                continue
            name = str(name)
            if name in result:
                raise ValueError(f"Duplicate channel row '{name}'")
            result[name] = row
        return result


class ConfigStoreFactory:
    def create(self, path: str | Path) -> ConfigStore:
        suffix = Path(path).suffix.lower()
        if suffix == ".json":
            return JsonConfigStore()
        if suffix == ".xlsx":
            return XlsxConfigStore()
        raise ValueError(f"Unsupported config format '{suffix}'")


def _read_xlsx_tables(path: Path) -> dict[str, list[dict[str, Any]]]:
    with zipfile.ZipFile(path) as archive:
        sheet_paths = _sheet_paths(archive)
        shared_strings = _shared_strings(archive)
        tables = {}
        for sheet_name, sheet_path in sheet_paths.items():
            rows = _read_sheet(archive, sheet_path, shared_strings)
            if not rows:
                tables[sheet_name] = []
                continue
            headers = [str(header).strip() if header is not None else "" for header in rows[0]]
            tables[sheet_name] = [
                {
                    headers[index]: value
                    for index, value in enumerate(row)
                    if index < len(headers) and headers[index]
                }
                for row in rows[1:]
                if any(value not in (None, "") for value in row)
            ]
        return tables


def _sheet_paths(archive: zipfile.ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_targets = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels
    }
    result = {}
    for sheet in workbook.findall(".//{*}sheet"):
        sheet_name = sheet.attrib["name"]
        rel_id = sheet.attrib[
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        ]
        target = rel_targets[rel_id]
        if target.startswith("/"):
            target = target[1:]
        if not target.startswith("xl/"):
            target = f"xl/{target}"
        result[sheet_name] = target
    return result


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings = []
    for item in root.findall(".//{*}si"):
        strings.append("".join(text.text or "" for text in item.findall(".//{*}t")))
    return strings


def _read_sheet(
    archive: zipfile.ZipFile,
    sheet_path: str,
    shared_strings: list[str],
) -> list[list[Any]]:
    root = ET.fromstring(archive.read(sheet_path))
    rows = []
    for row_xml in root.findall(".//{*}sheetData/{*}row"):
        cells = {}
        for cell_xml in row_xml.findall("{*}c"):
            ref = cell_xml.attrib.get("r", "")
            column_index = _column_index(ref)
            cells[column_index] = _cell_value(cell_xml, shared_strings)
        if cells:
            width = max(cells) + 1
            rows.append([cells.get(index) for index in range(width)])
    return rows


def _cell_value(cell_xml: ET.Element, shared_strings: list[str]) -> Any:
    cell_type = cell_xml.attrib.get("t")
    if cell_type == "inlineStr":
        text = cell_xml.find(".//{*}t")
        return text.text if text is not None else ""
    value = cell_xml.find("{*}v")
    if value is None or value.text is None:
        return None
    if cell_type == "s":
        return shared_strings[int(value.text)]
    if cell_type == "b":
        return value.text == "1"
    return _parse_scalar(value.text)


def _parse_scalar(value: str) -> Any:
    if value == "":
        return None
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    index = 0
    for char in letters:
        index = index * 26 + ord(char.upper()) - ord("A") + 1
    return index - 1


def _write_xlsx_tables(path: Path, tables: dict[str, list[list[Any]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet_names = list(tables)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types(sheet_names))
        archive.writestr("_rels/.rels", _root_rels())
        archive.writestr("xl/workbook.xml", _workbook(sheet_names))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_rels(sheet_names))
        for index, sheet_name in enumerate(sheet_names, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _worksheet(tables[sheet_name]))


def _content_types(sheet_names: list[str]) -> str:
    sheet_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index, _ in enumerate(sheet_names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{sheet_overrides}"
        "</Types>"
    )


def _root_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def _workbook(sheet_names: list[str]) -> str:
    sheets = "".join(
        f'<sheet name="{_xml_escape(sheet_name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, sheet_name in enumerate(sheet_names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheets}</sheets>"
        "</workbook>"
    )


def _workbook_rels(sheet_names: list[str]) -> str:
    rels = "".join(
        f'<Relationship Id="rId{index}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index, _ in enumerate(sheet_names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{rels}"
        "</Relationships>"
    )


def _worksheet(rows: list[list[Any]]) -> str:
    row_xml = "".join(
        f'<row r="{row_index}">'
        f"{''.join(_cell(row_index, column_index, value) for column_index, value in enumerate(row, start=1))}"
        "</row>"
        for row_index, row in enumerate(rows, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{row_xml}</sheetData>"
        "</worksheet>"
    )


def _cell(row_index: int, column_index: int, value: Any) -> str:
    if value is None:
        return ""
    ref = f"{_column_name(column_index)}{row_index}"
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"><v>{value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t>{_xml_escape(str(value))}</t></is></c>'


def _column_name(column_index: int) -> str:
    name = ""
    while column_index:
        column_index, remainder = divmod(column_index - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
