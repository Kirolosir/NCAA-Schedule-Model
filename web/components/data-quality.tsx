import { Bootstrap, Config, fmt } from '@/lib/model';

export function CutoffReference({config}:{config:Config}) {
  return config.historical_cutoff_npi!=null?<p className="field-note">Prior-year cutoff reference: <strong>{fmt(config.historical_cutoff_npi)}</strong> (coach-provided; year unconfirmed). This is a historical comparison, not this season’s qualifying line.</p>:null;
}

export function DataFreshness({data,config}:{data:Bootstrap;config:Config}) {
  return <div className="data-freshness" role="status">
    <span><strong>Ratings: {data.source.season}</strong> · snapshot through {data.source.cutoff}</span>
    <span>{config.results_updated?`Website results last applied ${new Date(config.results_updated.applied_at).toLocaleString()} · ${config.results_updated.year} results`:'Website results have not been applied to this plan.'}</span>
  </div>;
}

export function AccuracyPanel({data,config}:{data:Bootstrap;config:Config}) {
  const check=data.historical_accuracy;
  if(!check.available||!check.model||!check.baseline)return <section className="panel model-card"><div className="panel-heading"><h2>Historical accuracy check</h2></div><div className="model-text"><p>{check.reason}</p><p>Choose 2024 or 2025 to see results from a separate test season.</p></div></section>;
  const model=check.model,baseline=check.baseline;
  return <section className="panel model-card accuracy-panel"><div className="panel-heading"><h2>Historical accuracy check</h2><span className="count-pill">{model.games.toLocaleString()} held-out games</span></div><div className="model-text">
    {config.probability_model!=='historical'?<p>Your current setup uses retrospective probabilities. The check below applies to the historical model.</p>:config.probability_slope_scale!==1?<p>Your current probability sensitivity is {fmt(config.probability_slope_scale,2)}×. The check below measures the historical model at 1.00×.</p>:null}
    <p>Trained on {check.training_seasons?.join(' and ')} outcomes; tested on <strong>{check.holdout_season}</strong> outcomes using {check.predictor_season} ratings available through {check.predictor_cutoff}. Test outcomes did not enter model fitting. {check.excluded_games} games involving teams without prior ratings were excluded.</p>
    <div className="quality-table"><table><thead><tr><th>Measure</th><th>Historical model</th><th>Constant baseline</th></tr></thead><tbody>
      <tr><th>Log loss · lower is better</th><td>{fmt(model.log_loss)}</td><td>{fmt(baseline.log_loss)}</td></tr>
      <tr><th>Brier score · lower is better</th><td>{fmt(model.brier_score)}</td><td>{fmt(baseline.brier_score)}</td></tr>
      <tr><th>Most likely result correct</th><td>{fmt(model.accuracy*100,1)}%</td><td>{fmt(baseline.accuracy*100,1)}%</td></tr>
    </tbody></table></div>
    <p>Log loss penalizes confident mistakes. Brier score adds the squared errors in win, draw, and loss probabilities (0 is perfect). The baseline uses training-season draw frequency and equal win/loss chances. Accuracy splits credit when the most likely outcomes tie.</p>
    <h3>Do predicted win chances match results?</h3>
    <div className="quality-table"><table><thead><tr><th>Predicted chance band</th><th>Team forecasts</th><th>Average predicted</th><th>Actually won</th></tr></thead><tbody>{model.win_calibration.map(row=><tr key={row.lower}><th>{row.lower*100}–{row.upper*100}%</th><td>{row.count.toLocaleString()}</td><td>{row.predicted_win_rate===null?'—':`${fmt(row.predicted_win_rate*100,1)}%`}</td><td>{row.actual_win_rate===null?'—':`${fmt(row.actual_win_rate*100,1)}%`}</td></tr>)}</tbody></table></div>
    <p>{check.scope}</p>
    <p>These checks measure historical probability quality. They do not measure future scheduling accuracy or validate a user’s assumed outcomes.</p>
  </div></section>;
}
