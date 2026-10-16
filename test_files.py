import pandas as pd
import math

df = pd.DataFrame({'costo': [math.nan, 10.5, float('nan'), None]})
print(df)
for c in df['costo']:
    print(c, pd.isna(c))
