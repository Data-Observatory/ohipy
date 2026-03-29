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

function weightedAvg(pairs) {
  const valid = pairs.filter(([, , w]) => w > 0);
  if (!valid.length) return NaN;
  const sumW = valid.reduce((s, [, , w]) => s + w, 0);
  return valid.reduce((s, [, v, w]) => s + v * w, 0) / sumW;
}

function getGoalScore(goals, goalName) {
  const entry = goals.find((g) => g.name === goalName);
  if (!entry) return NaN;
  const dim = entry.dimension.find((d) => d.name === "score");
  if (!dim || dim.value === NA) return NaN;
  return dim.value;
}

function calcRegion(goals, weights) {
  // Step 1: aggregate subgoals -> parent scores
  const parentScores = {};
  for (const [parent, subs] of Object.entries(GOAL_HIERARCHY)) {
    const pairs = subs
      .map((sub) => [sub, getGoalScore(goals, sub), weights[sub] || 0])
      .filter(([, v]) => !isNaN(v));
    parentScores[parent] = pairs.length ? weightedAvg(pairs) : NaN;
  }

  // Step 2: weighted average of parents + standalone goals -> index
  const pairs = [];
  for (const [parent, score] of Object.entries(parentScores)) {
    if (!isNaN(score) && (weights[parent] || 0) > 0) {
      pairs.push([parent, score, weights[parent]]);
    }
  }
  for (const goal of STANDALONE_GOALS) {
    const score = getGoalScore(goals, goal);
    if (!isNaN(score) && (weights[goal] || 0) > 0) {
      pairs.push([goal, score, weights[goal]]);
    }
  }

  return weightedAvg(pairs);
}

// For UI breakdown: compute goal scores consistent with calcRegion's weighting logic.
// - Subgoals (e.g. FIS) come directly from the input goal entries.
// - Parent goals (FP, LE, SP, BD) are re-computed from subgoals using subgoal weights.
// - Standalone goals come directly from the input goal entries.
function calcRegionBreakdown(goals, weights) {
  const goalScores = {};

  // Subgoals and standalone: take the "score" dimension directly.
  for (const g of ALL_GOALS) {
    // Parent goals get filled below after aggregation.
    if (GOAL_HIERARCHY[g]) continue;
    goalScores[g] = getGoalScore(goals, g);
  }

  // Parents: aggregate their subgoals using the same logic as calcRegion.
  for (const [parent, subs] of Object.entries(GOAL_HIERARCHY)) {
    const pairs = subs
      .map((sub) => [sub, getGoalScore(goals, sub), weights[sub] || 0])
      .filter(([, v]) => !isNaN(v));
    goalScores[parent] = pairs.length ? weightedAvg(pairs) : NaN;
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

// Node.js support
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
