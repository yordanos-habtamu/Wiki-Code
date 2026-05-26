import re
import sys
import traceback

try:
    import sqlglot
    from sqlglot import exp
except ImportError:
    sqlglot = None
    exp = None

SQL_KEYWORDS = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|MERGE|DROP|TRUNCATE)\b", re.IGNORECASE)
TRIPLE_QUOTE_PATTERN = re.compile(r"(?:r|u|f|b|rf|fr)?('{3}|\"{3})(.*?)(?:\1)", re.DOTALL | re.IGNORECASE)
SINGLE_QUOTE_PATTERN = re.compile(r"(?:r|u|f|b|rf|fr)?(['\"])(.*?)(?:\1)", re.DOTALL | re.IGNORECASE)


class SQLLineageAnalyzer:
    def __init__(self):
        if sqlglot is None:
            print('[SQLLineageAnalyzer] sqlglot not installed, lineage analysis disabled', file=sys.stderr)

    def extract_sql_dependencies(self, sql_content, dialect='postgres'):
        if sqlglot is None:
            return []

        if not sql_content or not SQL_KEYWORDS.search(sql_content):
            return []

        try:
            expressions = sqlglot.parse(sql_content, read=dialect)
        except Exception as exc:
            sys.stderr.write(f"[SQLLineageAnalyzer] Skipping unparseable query block: {exc}\n")
            sys.stderr.flush()
            return []

        lineage = []
        for expression in expressions:
            try:
                expression = self._unwrap_with(expression)
                sources = self._extract_source_datasets(expression)
                target = self._extract_target_dataset(expression)
                if not sources or not target:
                    continue

                line_range = self._find_line_range(sql_content, expression)
                transformation_type = 'sql_query'

                lineage.append({
                    'source_datasets': sorted(set(sources)),
                    'target_dataset': target,
                    'transformation_type': transformation_type,
                    'line_range': line_range
                })
            except Exception as exc:
                sys.stderr.write(f"[SQLLineageAnalyzer] Failed to extract lineage from expression: {exc}\n")
                sys.stderr.flush()
                traceback.print_exc(file=sys.stderr)
                continue

        return lineage

    def _unwrap_with(self, expression):
        if exp is None:
            return expression
        if isinstance(expression, exp.With):
            return expression.this or expression
        return expression

    def _extract_source_datasets(self, expression):
        sources = set()
        if exp is None:
            return []

        cte_names = {
            self._normalize_dataset_name(cte.alias_or_name)
            for cte in expression.find_all(exp.CTE)
            if getattr(cte, 'alias_or_name', None)
        }

        for table in expression.find_all(exp.Table):
            name = self._normalize_dataset_name(getattr(table, 'name', None) or table.sql())
            if name and name not in cte_names:
                sources.add(name)

        return sorted(sources)

    def _extract_target_dataset(self, expression):
        if exp is None:
            return ''

        if isinstance(expression, exp.With):
            expression = expression.this or expression

        target = None
        if isinstance(expression, (exp.Insert, exp.Update, exp.Delete, exp.Merge)):
            if getattr(expression, 'this', None) is not None:
                target = getattr(expression.this, 'name', None) or expression.this.sql()
        elif isinstance(expression, exp.Create):
            target_expr = getattr(expression, 'this', None)
            if target_expr is not None:
                target = getattr(target_expr, 'name', None) or target_expr.sql()
        elif isinstance(expression, exp.Select):
            target = 'resultset'
        else:
            target = getattr(expression, 'alias', None) or 'resultset'

        return self._normalize_dataset_name(target)

    def _normalize_dataset_name(self, name):
        if not name:
            return ''
        if isinstance(name, str):
            return name.strip().lower()
        return str(name).strip().lower()

    def _find_line_range(self, sql_content, expression):
        try:
            sql_text = expression.sql(dialect='postgres')
            start = sql_content.lower().find(sql_text.lower())
            if start < 0:
                return '1-1'
            start_line = sql_content[:start].count('\n') + 1
            end_line = start_line + sql_text.count('\n')
            return f'{start_line}-{end_line}'
        except Exception:
            return '1-1'

    def extract_lineage_from_python_source(self, python_content, dialect='postgres'):
        results = []
        if not python_content:
            return results

        candidates = []
        candidates.extend([match[1] for match in TRIPLE_QUOTE_PATTERN.findall(python_content)])
        candidates.extend([match[1] for match in SINGLE_QUOTE_PATTERN.findall(python_content) if SQL_KEYWORDS.search(match[1])])
        candidates = list(dict.fromkeys(candidates))

        for candidate in candidates:
            if SQL_KEYWORDS.search(candidate):
                results.extend(self.extract_sql_dependencies(candidate, dialect=dialect))

        return results
