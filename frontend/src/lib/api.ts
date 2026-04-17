/**
 * api.ts — Shared API client for True Grind backend.
 */

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000') + '/api';

export interface PsdResult {
  n_particles: number;
  D10: number;
  D50: number;
  D90: number;
  mean_um: number;
  span: number;
  fines_pct: number;
  uniform_pct: number;
  boulders_pct: number;
  bimodal_flag: boolean;
  uniformity: 'good' | 'moderate' | 'poor';
}

export interface QualityWarning {
  code: string;
  severity: 'error' | 'warning' | 'info';
  message: string;
  tip: string;
}

export interface AnalyzeResponse {
  success: boolean;
  psd: PsdResult;
  grind_category: string;
  classification_message: string;
  scale_px_per_mm: number;
  n_clumps: number;
  n_silverskin: number;
  clump_ratio: number;
  quality_warnings?: QualityWarning[];
}

export interface RecommendPayload {
  current_d50: number;
  current_setting: number;
  brew_method: string;
  taste_notes?: string;
  taste_tags?: string[];
  water_temp_c?: number;
  extraction_time_s?: number;
  filter_type?: string;
  dose_g?: number;
  water_g?: number;
  num_pours?: number;
  agitation_level?: string;
}

export interface GrindRecommendation {
  direction: string;
  steps: number;
  from_setting: number;
  to_setting: number;
  message: string;
}

export interface SecondaryAdvice {
  shown: boolean;
  type: string | null;
  direction: string | null;
  message: string | null;
}

export interface BrewAnalysis {
  issues: string[];
  all_in_range: boolean;
  temp_status?: string;
  time_status?: string;
  ratio_status?: string;
  filter_status?: string;
}

export interface RecommendationResult {
  mode: string;
  brew_method: string;
  grind_recommendation: GrindRecommendation;
  secondary_advice: SecondaryAdvice;
  brew_analysis: BrewAnalysis;
  distribution: {
    fines_pct: number;
    uniform_pct: number;
    boulders_pct: number;
    bimodal_flag: boolean;
    uniformity: string;
  };
  confidence: {
    grind: string;
    secondary: string;
  };
  parsed_tags: string[];
  llm_enhanced?: boolean;
  llm_message?: string;
}

export interface RecommendResponse {
  success: boolean;
  recommendation: RecommendationResult;
}

export interface BrewMethodConfig {
  target_d50_um: number;
  ideal_temp_c: [number, number];
  ideal_extraction_time_s: [number, number];
  ideal_ratio: [number, number];
  filter_types: string[];
  description: string;
}

/**
 * Upload a photo for grind analysis.
 */
export async function analyzePhoto(file: File, brewMethod: string = 'pour_over', tiltAngleDeg: number = 0): Promise<AnalyzeResponse> {
  const formData = new FormData();
  formData.append('file', file);

  let url = `${API_BASE}/analyze?brew_method=${encodeURIComponent(brewMethod)}`;
  if (tiltAngleDeg > 0) {
    url += `&tilt_angle_deg=${tiltAngleDeg.toFixed(1)}`;
  }

  const resp = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Unknown error' }));
    const detail = err.detail;
    // If detail is an object with message + quality_warnings, attach warnings
    if (typeof detail === 'object' && detail.message) {
      const error: any = new Error(detail.message);
      error.quality_warnings = detail.quality_warnings || [];
      throw error;
    }
    throw new Error(typeof detail === 'string' ? detail : `Analysis failed (${resp.status})`);
  }

  return resp.json();
}

/**
 * Get grind adjustment recommendation.
 */
export async function getRecommendation(payload: RecommendPayload): Promise<RecommendResponse> {
  const resp = await fetch(`${API_BASE}/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `Recommendation failed (${resp.status})`);
  }

  return resp.json();
}

/**
 * Get LLM-enhanced grind recommendation (falls back to rule-based).
 */
export async function getLLMRecommendation(payload: RecommendPayload): Promise<RecommendResponse> {
  const resp = await fetch(`${API_BASE}/recommend-llm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    // Fallback to rule-based if LLM endpoint fails
    return getRecommendation(payload);
  }

  return resp.json();
}

/**
 * Get available brew methods and their ideal ranges.
 */
export async function getBrewMethods(): Promise<Record<string, BrewMethodConfig>> {
  const resp = await fetch(`${API_BASE}/brew-methods`);
  if (!resp.ok) throw new Error('Failed to load brew methods');
  const data = await resp.json();
  return data.brew_methods;
}

/**
 * Health check.
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const resp = await fetch(`${API_BASE}/health`);
    return resp.ok;
  } catch {
    return false;
  }
}

export interface PreflightResult {
  found: boolean;
  px_per_mm: number | null;
  quality: 'good' | 'ok' | 'too_far' | 'too_close' | 'not_found' | 'decode_error';
  message: string;
}

/**
 * Quick calibration check — runs quarter detection only (no YOLO).
 * ~0.1s response. Used after camera capture to give distance feedback.
 */
export async function preflightCheck(file: File): Promise<PreflightResult> {
  const formData = new FormData();
  formData.append('file', file);

  const resp = await fetch(`${API_BASE}/preflight`, {
    method: 'POST',
    body: formData,
  });

  if (!resp.ok) {
    return { found: false, px_per_mm: null, quality: 'decode_error', message: 'Preflight check failed.' };
  }

  return resp.json();
}
