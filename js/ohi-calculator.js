/**
 * OHI Index Calculator
 *
 * Calculates weighted Ocean Health Index scores from API response data (response2.json format).
 * Single-level weighting: all 10 goals weighted equally by default, user controls goal weights.
 * Values of -9999 are treated as missing (excluded from calculation).
 */

const NA = -9999;

const ALL_GOALS = ["AO", "BD", "CP", "CS", "CW", "FP", "LE", "NP", "SP", "TR"];

function getDefaultWeights() {
  const w = {};
  ALL_GOALS.forEach((g) => (w[g] = 1));
  return w;
}

function getGoalScore(goals, goalName) {
  const entry = goals.find((g) => g.name === goalName);
  if (!entry) return NaN;
  const dim = entry.dimension.find((d) => d.name === "score");
  if (!dim || dim.value === NA) return NaN;
  return dim.value;
}

function calcRegion(goals, weights) {
  let sumW = 0,
    sumVW = 0;
  for (const g of goals) {
    if (!ALL_GOALS.includes(g.name)) continue;
    const dim = g.dimension.find((d) => d.name === "score");
    if (!dim || dim.value === NA) continue;
    const w = weights[g.name] || 0;
    if (w > 0) {
      sumW += w;
      sumVW += dim.value * w;
    }
  }
  return sumW > 0 ? sumVW / sumW : NaN;
}

function calcRegionBreakdown(goals, weights) {
  const scoreOf = {};
  for (const g of goals) {
    if (!ALL_GOALS.includes(g.name)) continue;
    const dim = g.dimension.find((d) => d.name === "score");
    scoreOf[g.name] = dim && dim.value !== NA ? dim.value : NaN;
  }

  let sumW = 0,
    sumVW = 0;
  for (const goal of ALL_GOALS) {
    const v = scoreOf[goal];
    const w = weights[goal] || 0;
    if (w > 0 && !isNaN(v)) {
      sumW += w;
      sumVW += v * w;
    }
  }

  const index = sumW > 0 ? sumVW / sumW : NaN;
  return { index, goalScores: scoreOf };
}

function calcIndex(data, weights, year) {
  const scores = year
    ? data.data.scores.filter((y) => y.year === String(year))
    : data.data.scores;

  const results = {};
  for (const y of scores) {
    const regionResults = {};
    for (const comuna of y.comunes) {
      regionResults[comuna.idRegion] = calcRegion(comuna.goals, weights);
    }
    const vals = Object.values(regionResults).filter((v) => !isNaN(v));
    const global = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : NaN;
    results[y.year] = { regions: regionResults, global };
  }
  return results;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    getDefaultWeights,
    ALL_GOALS,
    calcIndex,
    calcRegionBreakdown,
  };
}
