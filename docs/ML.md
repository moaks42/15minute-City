# ML layer (Workstream B)

Code: `engine/app/ml.py`. Artifacts: `engine/models/archetypes.joblib` + `metrics.json`. They are retrained automatically whenever either city's `dataVersion` changes, at Docker build (`app.warmup`) or at startup.

## 1. Neighbourhood archetypes (pooled across Kraków and Praha)

**Labels come from unsupervised clustering.** The neural network only learns to reproduce those clusters, so that it can return a *soft* membership ("78% Student buzz") for any cell or district. Please say this plainly in the pitch.

| step | detail |
|---|---|
| Features | every `crossCity: true` indicator that has data in **both** cities (absolute values: minutes, departures/h, shares, dB, µg/m³, counts within a radius). No price, because the currencies differ. |
| Transform | `log1p` for heavy-tailed units (counts, departures/h, ha, m, km, /km²), then one `StandardScaler` fitted on the habitable cells of both cities together |
| Clustering | `KMeans(n_init=10, random_state=42)` for k = 6, 7, 8; keep the k with the best silhouette (on a 4,000-cell sample) |
| Classifier | `MLPClassifier(hidden_layer_sizes=(32, 16), early_stopping=True)`, stratified 80/20 split, trained on the cluster labels |
| Naming | each cluster centroid is matched to one of 8 archetype ids (`config/indicators.yaml → archetypes`) by Hungarian assignment against hand-written prototype directions (e.g. `green_residential` = high green share, short walk to a park, low noise). The API returns ids; C owns the names in pl/cs/en. |
| Output | `archetype: {id, p}` on ranked places, `probs` on `/place`, and district archetypes = population-weighted mean of the cell probabilities |

### Current metrics

> ⚠ Trained on **synthetic dev data** (`engine/app/devdata.py`); A's real data has not landed yet. These numbers only prove the pipeline runs. They will be replaced with the real-data run at M2.

| metric | value |
|---|---|
| cells (habitable, both cities) | 6,576 (train 5,260 / test 1,316) |
| features | 48 cross-city indicators |
| silhouette k=6 / 7 / 8 | 0.125 / 0.122 / 0.103 → **k = 6** |
| MLP holdout accuracy | **0.948** |
| archetypes in use | green_residential, urban_mix, historic_core, family_suburb, student_buzz, quiet_outskirts |

Share of habitable cells per archetype (synthetic data):

| archetype | Kraków | Praha |
|---|---|---|
| family_suburb | 26.8% | 17.6% |
| quiet_outskirts | 22.7% | 23.1% |
| urban_mix | 20.8% | 14.1% |
| historic_core | 18.5% | 10.8% |
| student_buzz | 10.5% | 7.3% |
| green_residential | 0.8% | 27.1% |

**Limitations.** A low silhouette (≈ 0.1) means the city is a continuum, not crisp clusters. That's expected for urban form, and it's why we show probabilities rather than hard labels. The prototype matching is a heuristic: check the names against the map, and if a label looks wrong, adjust `PROTOTYPES` in `ml.py`.

## 2. Similar places (same city): `/api/{city}/similar/{h3}`

Cosine similarity on the same standardized cross-city vectors, mapped to 0–1 as `(cos + 1) / 2`. The cell's own 2-ring (its immediate neighbours) is excluded, and results are diversified to at most 1 cell per neighbourhood.

## 3. Twin neighbourhoods (across cities): `/api/twins`

The same vector space is shared by both cities (pooled scaler), so Kraków → Praha (and back) is a plain cosine nearest-neighbour search:

- `h3=` → the top cells in the other city, at most 1 per neighbourhood (so you get Karlín, Vinohrady, Žižkov… rather than five adjacent hexes)
- `district=` → district vector = population-weighted mean of its cells, compared with every district of the other city
- `sharedTraits` = criteria where both places score ≥ 60 (≥ 55 for districts) within their own city

## 4. Preference learning (P2): `/api/{city}/prefs/pairs` + `/api/prefs/fit`

Six contrasting place profiles (each pair differs strongly on one criterion). Choices are fitted with Bradley–Terry, i.e. logistic regression on criterion-difference vectors with symmetric augmentation and no intercept. Positive coefficients are mapped to emoji levels 1–5 (the largest coefficient → 5); non-positive coefficients → 0 (skip). `confidence` = training accuracy, which is low with 6 answers by design. Present the result as a *suggestion*.
