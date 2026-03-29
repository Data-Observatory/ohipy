/**
 * OHI Index Calculator
 *
 * Calculates weighted Ocean Health Index scores from API response data (response2.json format).
 * Two-level weighting: subgoals -> parent, parents + standalone goals -> index.
 * Values of -9999 are treated as missing (excluded from calculation).
 */

const NA = -9999;

const GOAL_HIERARCHY = {
  FP: ["FIS", "MAR"],
  LE: ["LIV", "ECO"],
  SP: ["ICO", "LSP"],
  BD: ["HAB", "SPP"],
};

const STANDALONE_GOALS = ["AO", "NP", "CS", "CP", "TR", "CW"];

const ALL_GOALS = [
  ...Object.keys(GOAL_HIERARCHY),
  ...Object.values(GOAL_HIERARCHY).flat(),
  ...STANDALONE_GOALS,
];

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
  // Pre-index goals by name and extract score values (optimizations #1 + #2)
  const scoreOf = {};
  for (const g of goals) {
    const dim = g.dimension.find((d) => d.name === "score");
    scoreOf[g.name] = dim && dim.value !== NA ? dim.value : NaN;
  }

  // Step 1: aggregate subgoals -> parent scores (inlined weighted average, optimization #3)
  const parentScores = {};
  for (const [parent, subs] of Object.entries(GOAL_HIERARCHY)) {
    let sumW = 0,
      sumVW = 0;
    for (const sub of subs) {
      const v = scoreOf[sub];
      const w = weights[sub] || 0;
      if (w > 0 && !isNaN(v)) {
        sumW += w;
        sumVW += v * w;
      }
    }
    parentScores[parent] = sumW > 0 ? sumVW / sumW : NaN;
  }

  // Step 2: weighted average of parents + standalone goals -> index (inlined, optimization #3)
  let sumW = 0,
    sumVW = 0;
  for (const [parent, score] of Object.entries(parentScores)) {
    const w = weights[parent] || 0;
    if (w > 0 && !isNaN(score)) {
      sumW += w;
      sumVW += score * w;
    }
  }
  for (const goal of STANDALONE_GOALS) {
    const v = scoreOf[goal];
    const w = weights[goal] || 0;
    if (w > 0 && !isNaN(v)) {
      sumW += w;
      sumVW += v * w;
    }
  }

  return sumW > 0 ? sumVW / sumW : NaN;
}

function calcRegionBreakdown(goals, weights) {
  const scoreOf = {};
  for (const g of goals) {
    const dim = g.dimension.find((d) => d.name === "score");
    scoreOf[g.name] = dim && dim.value !== NA ? dim.value : NaN;
  }

  const goalScores = {};

  for (const g of ALL_GOALS) {
    if (GOAL_HIERARCHY[g]) continue;
    goalScores[g] = scoreOf[g];
  }

  for (const [parent, subs] of Object.entries(GOAL_HIERARCHY)) {
    let sumW = 0,
      sumVW = 0;
    for (const sub of subs) {
      const v = scoreOf[sub];
      const w = weights[sub] || 0;
      if (w > 0 && !isNaN(v)) {
        sumW += w;
        sumVW += v * w;
      }
    }
    goalScores[parent] = sumW > 0 ? sumVW / sumW : NaN;
  }

  const index = calcRegion(goals, weights);
  return { index, goalScores };
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
    GOAL_HIERARCHY,
    STANDALONE_GOALS,
    calcIndex,
    calcRegionBreakdown,
  };
}
