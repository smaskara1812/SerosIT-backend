"""Regenerates the legacy->new schema mapping doc used for the eventual
production data migration.

Two sources, both authoritative, neither hand-maintained:
  1. `SQL commands/import_*.sql` — the real INSERT INTO <new> (...) SELECT
     ... FROM Seros_Data.<legacy> statements used to import each table.
     These carry the actual column-for-column mapping, including the
     transforms (IF(...)/NULLIF/etc.) applied during import.
  2. Django model introspection — every table in the app plus its real
     db_column names and FK targets, so tables with no legacy source yet
     still show up as "needs a decision" rather than being silently
     missing.

Run it again any time new masters are added; it's a regeneration, not a
document to edit by hand:

    python manage.py build_migration_map > docs/migration_map.md
"""

import os
import re

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _legacy_columns(legacy_table):
    """Real column list of Seros_Data.<legacy_table>, straight from
    information_schema — same MySQL connection the app already uses, since
    Seros_Data lives on the same server (exactly what the import scripts'
    own `FROM Seros_Data.X` assumes). Returns None (not []) if the table
    can't be introspected, so callers can tell "no columns" from "couldn't
    check" rather than reporting a false 100%-skipped list."""
    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                "ORDER BY ORDINAL_POSITION",
                ["Seros_Data", legacy_table],
            )
            rows = [r[0] for r in cur.fetchall()]
        return rows or None
    except Exception:
        return None


def _referenced_legacy_columns(exprs, legacy_cols):
    """Which of the legacy table's real columns are actually touched by
    these SELECT expressions — a plain column reference or one buried in a
    transform like IF(X IN (...), NULL, X) both count. Matched
    case-insensitively since legacy is PascalCase and expressions are
    copied verbatim from the import SQL."""
    by_lower = {c.lower(): c for c in legacy_cols}
    touched = set()
    for expr in exprs:
        for tok in _IDENT_RE.findall(expr):
            hit = by_lower.get(tok.lower())
            if hit:
                touched.add(hit)
    return touched

# INSERT INTO <db>.<table> ( cols ) SELECT <exprs> FROM <db>.<legacy_table>
INSERT_RE = re.compile(
    r"INSERT\s+INTO\s+\w+\.(?P<new_table>\w+)\s*\((?P<cols>.*?)\)\s*"
    r"SELECT\s+(?P<exprs>.*?)\s+FROM\s+(?:\w+\.)?(?P<legacy_table>\w+)",
    re.IGNORECASE | re.DOTALL,
)

# UPDATE <db>.<new_table> <alias1> JOIN <db>.<legacy_table> <alias2> ON ...
# SET <alias1>.<col> = <alias2>.<expr>, ... — the backfill_*.sql pattern used
# for columns added to a model after its original import_*.sql already ran.
UPDATE_RE = re.compile(
    r"UPDATE\s+(?:\w+\.)?(?P<new_table>\w+)\s+(?P<alias1>\w+)\s*\n?\s*"
    r"JOIN\s+(?:\w+\.)?(?P<legacy_table>\w+)\s+(?P<alias2>\w+)\s+ON\s+.*?\s+"
    r"SET\s+(?P<sets>.*?);",
    re.IGNORECASE | re.DOTALL,
)


def _strip_sql_comments(text):
    text = re.sub(r"--[^\n]*", "", text)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def _split_top_level(text):
    """Split on commas that aren't inside parentheses — SELECT expressions
    like IF(a IN (1,2), NULL, a) contain their own commas."""
    parts, depth, current = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if "".join(current).strip():
        parts.append("".join(current).strip())
    return parts


def _merge_mapping(mappings, new_table, legacy_table, source_file, columns):
    """Add a table's column mapping, extending (not overwriting) any
    existing entry — a backfill_*.sql pass adds columns to a table an
    import_*.sql pass already mapped, and both source files matter."""
    existing = mappings.get(new_table)
    if existing is None or existing.get("warning"):
        mappings[new_table] = {
            "legacy_table": legacy_table,
            "source_files": [source_file],
            "columns": list(columns),
            "warning": None,
        }
        return
    existing["columns"].extend(columns)
    if source_file not in existing["source_files"]:
        existing["source_files"].append(source_file)


def _set_clause_columns(sets_text, alias1, alias2):
    """Parse `a.col = b.legacy_expr, a.col2 = b.expr2, ...` -> [(col, expr)]."""
    pairs = []
    for part in _split_top_level(sets_text):
        if "=" not in part:
            continue
        lhs, rhs = part.split("=", 1)
        lhs, rhs = lhs.strip(), rhs.strip()
        prefix = f"{alias1}."
        if lhs.startswith(prefix):
            lhs = lhs[len(prefix):]
        pairs.append((lhs, rhs))
    return pairs


def parse_import_sql(sql_dir):
    """-> {new_table: {"legacy_table": str, "source_files": [str], "columns": [(new, legacy_expr)], "warning": str|None}}

    Reads both `import_*.sql` (the original INSERT INTO ... SELECT ... FROM
    passes) and `backfill_*.sql` (later UPDATE ... JOIN ... SET passes for
    columns added to a model after its table was first imported), merging
    entries for the same table rather than letting the second file's parse
    overwrite the first's.
    """
    mappings = {}
    if not os.path.isdir(sql_dir):
        return mappings

    names = sorted(os.listdir(sql_dir))

    for name in names:
        if not name.startswith("import_") or not name.endswith(".sql"):
            continue
        with open(os.path.join(sql_dir, name)) as fh:
            content = _strip_sql_comments(fh.read())
        for m in INSERT_RE.finditer(content):
            new_table = m.group("new_table")
            cols = _split_top_level(m.group("cols"))
            exprs = _split_top_level(m.group("exprs"))
            if len(cols) != len(exprs):
                # Positional alignment is the whole basis of the mapping —
                # if the counts disagree, say so rather than emitting a
                # silently-wrong row-for-row guess.
                mappings[new_table] = {
                    "legacy_table": m.group("legacy_table"),
                    "source_files": [name],
                    "columns": [],
                    "warning": f"column/expression count mismatch ({len(cols)} vs {len(exprs)}) — verify by hand",
                }
                continue
            _merge_mapping(
                mappings, new_table, m.group("legacy_table"), name,
                list(zip(cols, exprs)),
            )

    for name in names:
        if not name.startswith("backfill_") or not name.endswith(".sql"):
            continue
        with open(os.path.join(sql_dir, name)) as fh:
            content = _strip_sql_comments(fh.read())
        for m in UPDATE_RE.finditer(content):
            new_table = m.group("new_table")
            pairs = _set_clause_columns(m.group("sets"), m.group("alias1"), m.group("alias2"))
            if not pairs:
                continue
            _merge_mapping(mappings, new_table, m.group("legacy_table"), name, pairs)

    return mappings


class Command(BaseCommand):
    help = "Regenerate the legacy->new schema migration map (writes Markdown to stdout)."

    def handle(self, *args, **options):
        sql_dir = os.path.join(settings.BASE_DIR, "SQL commands")
        imported = parse_import_sql(sql_dir)

        models = sorted(
            apps.get_app_config("core").get_models(), key=lambda m: m._meta.db_table
        )

        out = self.stdout.write
        out("# Legacy → SerosIT schema migration map")
        out("")
        out(
            "Generated by `python manage.py build_migration_map`. Do not edit by hand — "
            "re-run it instead, so it stays correct as new masters are added."
        )
        out("")
        out(
            "Column mappings come from the real `SQL commands/import_*.sql` statements "
            "used at import time, so any transform applied then (dangling-FK nulling, "
            "dedup, etc.) is visible in the Legacy column."
        )
        out("")

        with_source = [m for m in models if m._meta.db_table in imported]
        without_source = [m for m in models if m._meta.db_table not in imported]

        out(f"- Tables in this app: **{len(models)}**")
        out(f"- With a known legacy source: **{len(with_source)}**")
        out(f"- Without one (new tables, or not yet imported): **{len(without_source)}**")
        out("")

        out("## Tables with a known legacy source")
        out("")
        for model in with_source:
            table = model._meta.db_table
            info = imported[table]
            out(f"### `{table}`  ←  `Seros_Data.{info['legacy_table']}`")
            out("")
            sources = ", ".join(f"`SQL commands/{f}`" for f in info["source_files"])
            out(f"_Source: {sources}_")
            out("")
            if info["warning"]:
                out(f"> **WARNING:** {info['warning']}")
                out("")
                continue
            out("| New column | Legacy column / expression |")
            out("| --- | --- |")
            mapped_new_cols = set()
            all_exprs = []
            for new_col, legacy_expr in info["columns"]:
                flat = " ".join(legacy_expr.split())
                out(f"| `{new_col}` | `{flat}` |")
                mapped_new_cols.add(new_col)
                all_exprs.append(flat)
            out("")

            # New columns since import: real model columns the original
            # INSERT never mentioned — added by a later migration, so
            # every existing row has NULL/default there until backfilled.
            model_cols = [f.column for f in model._meta.fields]
            added_since = [c for c in model_cols if c not in mapped_new_cols]
            if added_since:
                out("**New columns added since import** (no legacy value — backfilled separately or left NULL):")
                out("")
                for c in added_since:
                    out(f"- `{c}`")
                out("")

            # Legacy columns never imported: real legacy columns that
            # never appeared in any SELECT expression for this table.
            legacy_cols = _legacy_columns(info["legacy_table"])
            if legacy_cols is None:
                out(f"_Could not introspect `Seros_Data.{info['legacy_table']}` to check for skipped legacy columns — verify by hand if that database isn't reachable here._")
                out("")
            else:
                referenced = _referenced_legacy_columns(all_exprs, legacy_cols)
                skipped = [c for c in legacy_cols if c not in referenced]
                if skipped:
                    out("**Legacy columns not imported** (exist in `Seros_Data`, deliberately or accidentally left out):")
                    out("")
                    for c in skipped:
                        out(f"- `{c}`")
                    out("")

        out("## Tables with no legacy source mapping")
        out("")
        out(
            "Either genuinely new to this system (start empty / seed by hand), or "
            "imported some other way. Check each model's docstring in "
            "`core/models.py` — this codebase documents that distinction per model."
        )
        out("")
        out("| Table | Model | Columns |")
        out("| --- | --- | --- |")
        for model in without_source:
            cols = ", ".join(f"`{f.column}`" for f in model._meta.fields)
            out(f"| `{model._meta.db_table}` | `{model.__name__}` | {cols} |")
        out("")

        out("## FK dependency order (insert parents before children)")
        out("")
        out(
            "Self-referential tables are marked — insert those with the parent column "
            "NULL first, then a second UPDATE pass once every row exists."
        )
        out("")
        for i, (table, self_ref) in enumerate(self._fk_order(models), 1):
            out(f"{i}. `{table}`" + ("  _(self-referential)_" if self_ref else ""))
        out("")

    def _fk_order(self, models):
        """Topological sort on real FK dependencies -> [(table, is_self_ref)]."""
        by_table = {m._meta.db_table: m for m in models}
        deps, self_ref = {t: set() for t in by_table}, set()
        for model in models:
            table = model._meta.db_table
            for f in model._meta.get_fields():
                if not (f.many_to_one or (getattr(f, "one_to_one", False) and getattr(f, "concrete", False))):
                    continue
                if not (f.concrete and f.related_model):
                    continue
                target = f.related_model._meta.db_table
                if target == table:
                    self_ref.add(table)
                elif target in by_table:
                    deps[table].add(target)

        order, remaining = [], dict(deps)
        while remaining:
            ready = sorted(t for t, d in remaining.items() if not d)
            if not ready:
                # Shouldn't happen given the self-ref carve-out above, but a
                # real cycle must be reported, not silently truncated.
                for t in sorted(remaining):
                    order.append((t, t in self_ref))
                break
            for t in ready:
                order.append((t, t in self_ref))
                del remaining[t]
            for d in remaining.values():
                d -= set(ready)
        return order
