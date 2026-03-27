/**
 * Ocean Health Index Calculator - Pure JavaScript implementation
 * Based on OHI Python calculation library
 */

/**
 * Parent goals with their subgoals (two-level weighting)
 */
const GOAL_HIERARCHY = {
  FP: { subgoals: ['FIS', 'MAR'] },
  LE: { subgoals: ['LIV', 'ECO'] },
  SP: { subgoals: ['ICO', 'LSP'] },
  BD: { subgoals: ['HAB', 'SPP'] }
};

/**
 * Standalone goals (no subgoals)
 */
const STANDALONE_GOALS = ['AO', 'NP', 'CS', 'CP', 'TR', 'CW'];

/**
 * All 18 goals
 */
const ALL_GOALS = [
  'FP', 'FIS', 'MAR',
  'AO', 'NP', 'CS', 'CP', 'TR',
  'LE', 'LIV', 'ECO',
  'SP', 'ICO', 'LSP',
  'CW', 'BD', 'HAB', 'SPP'
];

/**
 * Calculate weighted average excluding zero-weight items.
 * @param {number[]} values - Array of numeric values
 * @param {number[]} weights - Array of weights (same length as values)
 * @returns {number} Weighted average, or NaN if all weights are zero
 * @example
 * weightedAverage([80, 60], [1, 1]) // returns 70
 * weightedAverage([80, 60], [1, 0]) // returns 80
 * weightedAverage([10, 20, 30], [0, 1, 1]) // returns 25
 */
function weightedAverage(values, weights) {
  if (values.length !== weights.length) {
    throw new Error('Values and weights arrays must have the same length');
  }

  const validValues = [];
  const validWeights = [];

  for (let i = 0; i < values.length; i++) {
    if (weights[i] > 0) {
      validValues.push(values[i]);
      validWeights.push(weights[i]);
    }
  }

  if (validWeights.length === 0) {
    return NaN;
  }

  const sumWeighted = validValues.reduce((sum, value, i) => {
    return sum + (value * validWeights[i]);
  }, 0);

  const sumWeights = validWeights.reduce((sum, weight) => sum + weight, 0);

  return sumWeighted / sumWeights;
}

/**
 * Validate weights are in range 0-20.
 * @param {Object} weights - Object with goal codes as keys and weights as values
 * @returns {{ valid: boolean, errors: string[] }} Validation result
 * @example
 * validateWeights({ FIS: 1, MAR: 2 }) // returns { valid: true, errors: [] }
 * validateWeights({ FIS: -1 }) // returns { valid: false, errors: ['FIS must be between 0 and 20'] }
 */
function validateWeights(weights) {
  const errors = [];

  for (const [goal, weight] of Object.entries(weights)) {
    if (weight < 0 || weight > 20) {
      errors.push(`${goal} must be between 0 and 20 (got ${weight})`);
    }
  }

  return {
    valid: errors.length === 0,
    errors
  };
}

/**
 * Get default weights for all goals (weight = 1.0 for all).
 * @returns {Object} Default weights object
 * @example
 * getDefaultWeights() // returns { FIS: 1, MAR: 1, AO: 1, ... }
 */
function getDefaultWeights() {
  const weights = {};
  for (const goal of ALL_GOALS) {
    weights[goal] = 1.0;
  }
  return weights;
}

/**
 * Aggregate subgoal scores to parent goal score.
 * Parent goal score is the weighted average of its subgoals.
 * @param {Object} regionScores - Region scores (goal codes to scores)
 * @param {Object} weights - Weights for goals
 * @param {string} parentGoal - Parent goal code (FP, LE, SP, or BD)
 * @returns {number} Parent goal score (0-100)
 * @example
 * aggregateSubgoalsToParent({ FIS: 80, MAR: 60 }, { FIS: 1, MAR: 1 }, 'FP') // returns 70
 */
function aggregateSubgoalsToParent(regionScores, weights, parentGoal) {
  const subgoals = GOAL_HIERARCHY[parentGoal].subgoals;
  const subgoalScores = [];
  const subgoalWeights = [];

  for (const subgoal of subgoals) {
    if (regionScores.hasOwnProperty(subgoal) && weights[subgoal] > 0) {
      subgoalScores.push(regionScores[subgoal]);
      subgoalWeights.push(weights[subgoal]);
    }
  }

  if (subgoalWeights.length === 0) {
    return NaN;
  }

  const sumWeighted = subgoalScores.reduce((sum, score, i) => {
    return sum + (score * subgoalWeights[i]);
  }, 0);

  const sumWeights = subgoalWeights.reduce((sum, weight) => sum + weight, 0);

  return sumWeighted / sumWeights;
}

/**
 * Calculate the index score for a single region.
 * Steps:
 * 1. Aggregate subgoals to parents (FP, LE, SP, BD)
 * 2. Calculate weighted average of: parent goals + standalone goals
 * @param {Object} regionScores - Region scores (goal codes to scores)
 * @param {Object} weights - Weights for goals
 * @returns {number} Region index score (0-100)
 * @example
 * calculateRegionIndex({ FIS: 80, MAR: 60, AO: 70 }, { FIS: 1, MAR: 1, AO: 1 })
 * // returns (70 (FP) + 70) / 2 = 70
 */
function calculateRegionIndex(regionScores, weights) {
  const parentScores = {};
  const parentGoals = ['FP', 'LE', 'SP', 'BD'];

  // Step 1: Aggregate subgoals to parent goals
  for (const goal of parentGoals) {
    parentScores[goal] = aggregateSubgoalsToParent(regionScores, weights, goal);
  }

  // Step 2: Collect scores for index calculation
  // For parent goals (FP, LE, SP, BD), use aggregated parent scores
  // For subgoals and standalone goals, use direct scores
  const indexScores = [];
  const indexWeights = [];

  // Parent goals contribute to index with their own weights
  for (const goal of parentGoals) {
    const weight = weights[goal];
    if (weight > 0 && !isNaN(parentScores[goal])) {
      indexScores.push(parentScores[goal]);
      indexWeights.push(weight);
    }
  }

  // Standalone goals contribute directly with their weights
  for (const goal of STANDALONE_GOALS) {
    const weight = weights[goal];
    if (weight > 0 && regionScores.hasOwnProperty(goal) && !isNaN(regionScores[goal])) {
      indexScores.push(regionScores[goal]);
      indexWeights.push(weight);
    }
  }

  if (indexWeights.length === 0) {
    return NaN;
  }

  const sumWeighted = indexScores.reduce((sum, score, i) => sum + (score * indexWeights[i]), 0);
  const sumWeights = indexWeights.reduce((sum, w) => sum + w, 0);

  return sumWeighted / sumWeights;
}

/**
 * Calculate index scores for all regions.
 * @param {Object} allData - Object mapping region IDs to region scores
 *   format: { "1101": { FIS: 80, MAR: 60, AO: 70, ... }, "1102": {...}, ... }
 * @param {Object} weights - Weights for goals
 * @returns {{ regions: Object, global: number }} Results with region scores and global average
 * @example
 * calculateAllRegions(
 *   { "1101": { FIS: 80, MAR: 60, AO: 70 }, "1102": { FIS: 70, MAR: 80, AO: 80 } },
 *   { FIS: 1, MAR: 1, AO: 1 }
 * )
 * // returns { regions: { "1101": 70, "1102": 77.5 }, global: 73.75 }
 */
function calculateAllRegions(allData, weights) {
  const regions = {};
  const regionScores = [];

  for (const [regionId, scores] of Object.entries(allData)) {
    const index = calculateRegionIndex(scores, weights);
    regions[regionId] = index;
    regionScores.push(index);
  }

  const global = regionScores.reduce((sum, score) => sum + score, 0) / regionScores.length;

  return {
    regions,
    global
  };
}

module.exports = {
  weightedAverage,
  validateWeights,
  getDefaultWeights,
  aggregateSubgoalsToParent,
  calculateRegionIndex,
  calculateAllRegions,
  GOAL_HIERARCHY,
  STANDALONE_GOALS,
  ALL_GOALS
};
