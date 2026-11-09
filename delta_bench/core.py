"""CSV validation and baseline-referenced tolerance comparison."""
import csv
import math
from pathlib import Path


class InputError(ValueError):
    """An input cannot be compared safely."""


def read_csv(path, key):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        header = reader.fieldnames
        if not header or any(not name for name in header) or len(set(header)) != len(header):
            raise InputError(f'{path}: missing, empty or duplicate headers')
        if key not in header:
            raise InputError(f'{path}: missing key column {key!r}')
        rows = {}
        for line, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise InputError(f'{path}:{line}: inconsistent row width')
            value = row[key]
            if not value.strip() or value in rows:
                raise InputError(f'{path}:{line}: empty or duplicate key {value!r}')
            rows[value] = row
        if not rows:
            raise InputError(f'{path}: no data rows')
        return header, rows


def number(raw, context):
    try:
        value = float(raw)
    except (ValueError, TypeError) as exc:
        raise InputError(f'{context}: not a number: {raw!r}') from exc
    if not math.isfinite(value):
        raise InputError(f'{context}: nonfinite number')
    return value


def compare(baseline, candidate, key, columns, atol=0.0, rtol=0.0):
    """Pass when abs(candidate-baseline) <= atol + rtol*abs(baseline)."""
    atol, rtol = number(atol, 'atol'), number(rtol, 'rtol')
    if min(atol, rtol) < 0:
        raise InputError('tolerances must be nonnegative')
    if not columns or len(set(columns)) != len(columns) or key in columns:
        raise InputError('select distinct numeric columns excluding the key')
    bh, br = read_csv(baseline, key)
    ch, cr = read_csv(candidate, key)
    for col in columns:
        if col not in bh or col not in ch:
            raise InputError(f'missing selected column {col!r}')
    # Validate even unmatched rows; invalid values must never evade the gate.
    parsed = []
    for label, rows in [('baseline', br), ('candidate', cr)]:
        parsed.append({k: {c: number(row[c], f'{label}/{k}/{c}') for c in columns}
                       for k, row in rows.items()})
    bn, cn = parsed
    missing, additional = sorted(br.keys() - cr.keys()), sorted(cr.keys() - br.keys())
    common = sorted(br.keys() & cr.keys())
    stats, mismatches = {}, []
    for col in columns:
        differences = []
        count = 0
        for row_key in common:
            before, after = bn[row_key][col], cn[row_key][col]
            delta = abs(after - before)
            limit = atol + rtol * abs(before)
            if not math.isfinite(delta) or not math.isfinite(limit):
                raise InputError(f'{row_key}/{col}: floating-point range exceeded')
            differences.append(delta)
            if delta > limit:
                count += 1
                mismatches.append(dict(key=row_key, column=col, baseline=before,
                                       candidate=after, abs_difference=delta, tolerance=limit))
        n = len(differences)
        stats[col] = dict(count=n, mismatches=count, passed=count == 0 and n > 0,
                          mae=math.fsum(d / n for d in differences) if n else None,
                          rmse=math.hypot(*(d / math.sqrt(n) for d in differences)) if n else None,
                          max_difference=max(differences) if n else None)
    return dict(schema_version=1, passed=bool(common) and not (missing or additional or mismatches),
                baseline=str(baseline), candidate=str(candidate), key_column=key,
                atol=atol, rtol=rtol, compared_rows=len(common), baseline_rows=len(br),
                candidate_rows=len(cr), missing_rows=missing, additional_rows=additional,
                columns=stats, mismatches=mismatches)
