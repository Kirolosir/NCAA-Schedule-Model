export type Outcome = 'win' | 'tie' | 'loss';
export type Probabilities = Record<Outcome, number>;
export type Candidate = {team: string; recent_npi?: number; probabilities?: Probabilities};
export type FixedGame = {team: string; category?: string; result?: Outcome; probabilities?: Probabilities};
export type Band = {label: string; lower: number | null; upper: number | null; member_count?: number; representatives?: string[]};
export type Config = {
  season: string; probability_model: 'historical' | 'retrospective';
  target_team: string; mode: 'teams' | 'bands'; band_scale: 'rating' | 'rank';
  fixed_games: FixedGame[]; candidates: Candidate[]; bands: Band[];
  representatives_per_band: number; open_slots: number; required: string[]; excluded: string[];
  samples: number; validation_samples: number; insight_samples: number; top_n: number;
  seed: number; max_combinations: number; probability_slope_scale: number; convergence_tolerance: number;
  target_recent_npi?: number;
};
export type Summary = {mean: number; p10: number; p90: number; samples: number; mean_standard_error: number; mean_ci95: [number, number]};
export type Risk = {team: string; probabilities: Probabilities; expected_impact: Summary; swing_win_minus_loss: number}
  & Record<Outcome, {npi: Summary; impact: Summary}>;
export type Schedule = {rank: number; opponents: string[]; projection: Summary; impact_vs_fixed_slate: Summary;
  paired_gap_from_leader: Summary; stress_all_unlocked_wins: number; stress_all_unlocked_losses: number;
  opponent_impacts: Risk[]; reasoning: string[]};
export type Report = {config: Config; target_team: string; top_schedules: Schedule[]; validated_finalists: Schedule[];
  screening: unknown[]; standalone_opponents: Risk[]; baseline_projection: Summary; bands: Band[];
  division_solves: number; source: {cutoff: string}; limitations: string[]};
export type HistoryRow = {season:string; npi:number|null; record:string|null; cutoff:string; rating_kind:string};
export type Team = {name: string; npi: number; rank: number; record: string; history:HistoryRow[]};
export type SeasonSource = {season:string; cutoff:string; snapshot:string; rating_kind:string; eligible_npi_teams:number; eligible_npi_games:number; validation:{max_published_error?:number; iterations?:number; published_npi_available?:boolean}};
export type Bootstrap = {config: Config; teams: Team[]; source: SeasonSource; seasons:SeasonSource[]; report: Report | null;
  deployment?: {hosted: boolean; max_job_minutes: number};
  rating_range:[number,number]; model_diagnostics?:{holdout_log_loss:number;constant_holdout_log_loss:number;recent_only_holdout_log_loss:number;note:string};
  model: {slope: number; tie_log_weight: number; fit_log_loss: number; sample_count: number;method:string;training_seasons:string[];holdout_season:string|null;out_of_time_log_loss:number|null}};
export type Validation = {candidate_count: number; combinations: number; bands: Band[]; candidates: Candidate[]};
export type Job = {id: string; status: string; message: string; progress: number; report?: Report; config: Config};
export type Explore = {opponent_npi: number; baseline_npi: number; probabilities: Probabilities;
  outcomes: Record<Outcome, {npi: number; impact: number; game_value?: {total: number; quality_win_bonus: number}}>;
  curve: {npi: number; outcomes: Record<Outcome, {impact: number}>}[]};
export async function api<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/${path}`, {signal, ...(body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
  })});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The model could not complete this request.');
  return data as T;
}
export const fmt = (value?: number, digits = 3) => Number.isFinite(value) ? value!.toFixed(digits) : '—';
export const signed = (value?: number) => Number.isFinite(value) ? `${value! >= 0 ? '+' : ''}${fmt(value)}` : '—';
