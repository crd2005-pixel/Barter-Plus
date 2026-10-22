import re
text = "CODIGO1 $ 100.00\nCODIGO2 200.00\nCODIGO3 $ 300.00"

lines = text.split('\n')
data = []
for line in lines:
    parts = []
    # If the line has code + space + $, we should split it. Usually split('  ') handles visual gaps.
    # But for raw lines, split by explicit $ is better if no double space exists.
    if ' $' in line:
        parts = line.split(' $')
        parts[1] = '$' + parts[1]
    else:
        parts = line.split()
    data.append([p.strip() for p in parts if p.strip()])

print(data)
