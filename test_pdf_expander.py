import re

def _expand_multiline_pdf_row(row):
    multi_line = False
    max_splits = 0
    col_splits = []

    # 1. Detect max_splits
    for cell in row:
        val = str(cell).strip() if cell else ""
        if not val: continue
        parts = [p.strip() for p in val.split('\n') if p.strip() and p.strip() != '$']
        prices = re.findall(r'\d{1,3}(?:\.\d{3})+(?:,\d+)?', val)
        if len(prices) > 1:
            max_splits = max(max_splits, len(prices))
        if len(parts) > 1:
            max_splits = max(max_splits, len(parts))

    if max_splits <= 1:
        return [row]

    # 2. Populate col_splits
    for cell in row:
        val = str(cell).strip() if cell else ""
        if not val:
            col_splits.append([])
            continue

        parts = [p.strip() for p in val.split('\n') if p.strip() and p.strip() != '$']

        # Test if it's a "messy" price column where parts don't match max_splits, but regex prices do
        prices = re.findall(r'\d{1,3}(?:\.\d{3})+(?:,\d+)?', val)
        if len(prices) == max_splits:
            col_splits.append(prices)
        else:
            col_splits.append(parts)

    expanded_rows = []
    for i in range(max_splits):
        new_row = []
        for col_parts in col_splits:
            if not col_parts:
                new_row.append("")
            elif len(col_parts) == max_splits:
                new_row.append(col_parts[i])
            elif len(col_parts) == 1:
                new_row.append(col_parts[0])
            else:
                new_row.append(" ".join(col_parts))
        expanded_rows.append(new_row)

    return expanded_rows

row_baterias = [
    "UB 450\nM40FD\nM18FD",
    "12X45\n12X40\n12X50",
    "WILLARD\nMOURA\nMOURA",
    "ford k fiesta - ecosport -\nagile - fiorino",
    "$\n$ 105.361\n71.187\n120.000",  # Added one more to match 3 splits? Wait, the regex captures 105.361, 71.187, 120.000
    "$ 97.111\n$ 109.628\n$ 122.262"
]
for r in _expand_multiline_pdf_row(row_baterias):
    print(r)
