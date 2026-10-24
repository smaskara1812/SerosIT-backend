"""Spreadsheet formula injection. A text that starts with = + - or @ is run as a formula when the file is opened in Excel (a stored
`=HYPERLINK("http://...")` or `=cmd|...` in a remark becomes live in the export). Every CSV and Excel export of free text goes through here:
such a text is written with a leading apostrophe (CSV, the usual convention) or as plain text (Excel). Real numbers, and texts that are just a
signed number ("-5.2"), are left alone."""

import csv
import re

_NUMBER = re.compile(r"^[+-]?\d+([.,]\d+)?$")
_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value):
    if isinstance(value, str) and value.startswith(_DANGEROUS) and not _NUMBER.match(value.strip()):
        return "'" + value
    return value


class _Writer:
    def __init__(self, writer):
        self._w = writer
        self.dialect = writer.dialect

    def writerow(self, row):
        return self._w.writerow([csv_safe(v) for v in row])

    def writerows(self, rows):
        for r in rows:
            self.writerow(r)


def writer(fileobj, *args, **kwargs):
    """csv.writer that neutralises formulas."""
    return _Writer(csv.writer(fileobj, *args, **kwargs))


class DictWriter(csv.DictWriter):
    """csv.DictWriter that neutralises formulas."""

    def writerow(self, rowdict):
        return super().writerow({k: csv_safe(v) for k, v in rowdict.items()})

    def writerows(self, rowdicts):
        for r in rowdicts:
            self.writerow(r)


def xlsx_neutralise(cell):
    """Make an openpyxl cell hold text, never a formula, when its value is a string that would be read as one."""
    v = cell.value
    if isinstance(v, str) and v.startswith(_DANGEROUS) and not _NUMBER.match(v.strip()):
        cell.data_type = "s"
        if v[:1] in ("\t", "\r"):
            cell.value = "'" + v
    return cell
