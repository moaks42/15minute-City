# ML layer (Workstream B)

Code: `engine/app/ml.py`. Artifacts: `engine/models/archetypes.joblib` + `metrics.json`. They are retrained automatically whenever either city's `dataVersion` changes, at Docker build (`app.warmup`) or at startup.

## 1. Neighbourhood archetypes (pooled across Kraków and Praha)

**Labels come from unsupervised clustering.** The neural network only learns to reproduce those clusters, so that it can return a *soft* membership ("78% Student buzz") for any cell or district. Please say this plainly in the pitch.

| step | detail |
|---|---|
| Features | every `crossCity: true` indicator that has data in **both** cities (absolute values: minutes, departures/h, shares, counts within a radius): **44 columns** on the real data. Excluded: price (currencies differ), and noise + PM2.5/PM10, because a city-level offset dominates them (K noise is Lden, P is LAeq; Kraków's regional PM is higher). With them in, the clusters split by city (one archetype 38% K / 0% P), which breaks shared archetypes and twins. |
| Transform | `log1p` for heavy-tailed units (counts, departures/h, ha, m, km, /km²), then one `StandardScaler` fitted on the habitable cells of both cities together |
| Clustering | `KMeans(n_init=10, random_state=42)` for k = 6, 7, 8 (silhouette on a 4,000-cell sample); take the **largest k whose silhouette is within 0.005 of the best** (scores are practically equal; finer types are more useful) |
| Classifier | `MLPClassifier(hidden_layer_sizes=(32, 16), early_stopping=True)`, stratified 80/20 split, trained on the cluster labels |
| Naming | explicit, ordered rules on the centroid z-scores (`ml.name_cluster`): very dense + culture close → `historic_core`; dense (food, nightlife, shops) → `urban_mix`; university close + nightlife → `student_buzz`; much industrial land → `industrial_edge`; services far away → `quiet_outskirts`; playgrounds + shops → `estate_blocks`; green share/forest → `green_residential`; frequent transit → `urban_mix`; otherwise `family_suburb`. Several clusters may share an id (their probabilities are summed). The rules were checked against the real neighbourhoods (table below). The API returns ids; C owns the names. |
| Output | `archetype: {id, p}` on ranked places, `probs` on `/place`, and district archetypes = population-weighted mean of the cell probabilities |

### Current metrics (real data from A, both cities)

| metric | value |
|---|---|
| cells (habitable, both cities) | 5,129 (train 4,103 / test 1,026) |
| features | 44 cross-city indicators |
| silhouette k = 6 / 7 / 8 | 0.103 / 0.104 / 0.102 → **k = 8** (within 0.005 of the best) |
| MLP holdout accuracy | **0.923** |
| archetypes in use | 5 of 8: `urban_mix`, `estate_blocks`, `family_suburb`, `green_residential`, `quiet_outskirts` (`historic_core`, `student_buzz`, `industrial_edge` don't emerge as separate clusters) |

| archetype | Kraków | Praha | typical neighbourhoods (K / P) |
|---|---|---|---|
| urban_mix | 17.9% | 35.2% | Nowa Huta, Grzegórzki, Łobzów, Stare Podgórze / Žižkov, Vinohrady, Holešovice, Smíchov, Libeň |
| estate_blocks | 23.6% | 15.5% | Wola Duchacka, Kabel, Ruczaj, Azory / Stodůlky, Chodov, Háje, Modřany |
| family_suburb | 17.4% | 35.9% | Grębałów, Mydlniki, Lasówka / Horní Počernice, Uhříněves, Újezd nad Lesy, Radotín |
| green_residential | 15.5% | 9.2% | Wola Justowska, Zwierzyniec, Pychowice / Dejvice, Troja, Kunratice |
| quiet_outskirts | 25.5% | 4.3% | Łuczanowice, Kostrze, Ruszcza / Lipence, Točná, Přední Kopanina |

Twins sanity check: Kazimierz (Kraków) → Žižkov 0.69, Vinohrady 0.59, Karlín 0.59, Staré Město 0.58, Josefov 0.57; district Stare Miasto → Praha 1 0.58, Praha 2 0.54 (distance similarity, §2).

**Limitations.** The MLP is very confident (p ≈ 1 in cluster cores) because it learns hard cluster labels; treat p as "how typical", not as a calibrated probability. A low silhouette (≈ 0.1) means the city is a continuum, not crisp clusters. That's expected for urban form, and it's why we show probabilities rather than hard labels. The prototype matching is a heuristic: check the names against the map, and if a label looks wrong, adjust the rules in `ml.name_cluster`.

## 2. Similar places (same city): `/api/{city}/similar/{h3}`

Distance similarity on the same standardized cross-city vectors: `similarity = 1 − d / d_ref`, where `d` is the Euclidean distance and `d_ref` the median distance between two random habitable cells (4,000 seeded pairs, per city pair; `ml.calibrate`). So **0 % = as alike as two random places, 100 % = identical**; values below 0 are shown as 0 but still ranked. The cell's own 2-ring (its immediate neighbours) is excluded, and results are diversified to at most 1 cell per neighbourhood.

Why not cosine: cosine ignores how *strongly* a place shows its profile (z-vector norms range from ~4 to ~13), and the old `(cos + 1) / 2` mapping made an unrelated random place look ≈ 48 % similar and the top twins ≈ 86 %.

## 3. Twin neighbourhoods (across cities): `/api/twins`

The same vector space is shared by both cities (pooled scaler), so Kraków → Praha (and back) is a plain nearest-neighbour search with the distance similarity above:

- `h3=` → the top cells in the other city, at most 1 per neighbourhood (so you get Karlín, Vinohrady, Žižkov… rather than five adjacent hexes)
- `district=` → district vector = population-weighted mean of its cells, compared with every district of the other city (`d_ref` = median distance between district vectors, since averages lie closer together than single cells)
- `sharedTraits` = criteria where both places score ≥ 60 (≥ 55 for districts) within their own city

## 4. Preference learning (P2): `/api/{city}/prefs/pairs` + `/api/prefs/fit`

Six contrasting place profiles (each pair differs strongly on one criterion). Choices are fitted with Bradley–Terry, i.e. logistic regression on criterion-difference vectors with symmetric augmentation and no intercept. Positive coefficients are mapped to emoji levels 1–5 (the largest coefficient → 5); non-positive coefficients → 0 (skip). `confidence` = training accuracy, which is low with 6 answers by design. Present the result as a *suggestion*.
