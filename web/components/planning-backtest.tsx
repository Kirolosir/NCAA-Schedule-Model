import { Bootstrap, Config, fmt } from '@/lib/model';

export function PlanningBacktestPanel({data,config}:{data:Bootstrap;config:Config}) {
  const test=data.planning_backtest;
  if(!test.available||!test.model||!test.baseline||!test.single_season_model)return <section className="panel model-card"><div className="panel-heading"><h2>Planning backtest</h2></div><div className="model-text"><p>{test.reason}</p></div></section>;
  const model=test.model,prior=test.single_season_model,baseline=test.baseline;
  const delta=prior.log_loss-model.log_loss;
  return <section className="panel model-card accuracy-panel"><div className="panel-heading"><h2>Planning backtest</h2><span className="count-pill">{model.games.toLocaleString()} held-out games</span></div><div className="model-text">
    <p><strong>What could we have predicted before {test.holdout_season}?</strong> The replay builds strengths as of {test.as_of_season}, using the same function as the planner, then predicts the {test.holdout_season} outcomes. Probability fitting uses {test.training_seasons?.join(' and ')} outcomes only.</p>
    <ul className="backtest-sources">{test.strength_sources?.map(source=><li key={source.season}>{source.season} snapshot · {source.weight*100}% weight · through {source.cutoff}</li>)}</ul>
    <p>The pre-2024 ratings are retrospective reconstructions from historical results.</p>
    {!test.complete_three_season_blend&&<p>This older replay uses the app’s one-snapshot fallback. Select 2025 to check the complete three-season blend.</p>}
    {config.probability_model!=='historical'||config.probability_slope_scale!==1?<p>The scores below apply to the default historical model at 1.00×. Your current model or sensitivity setting differs.</p>:null}
    <div className="quality-table"><table><thead><tr><th>Measure</th><th>Planning inputs</th><th>Prior snapshot only</th><th>Constant baseline</th></tr></thead><tbody>
      <tr><th>Log loss ↓</th><td>{fmt(model.log_loss)}</td><td>{fmt(prior.log_loss)}</td><td>{fmt(baseline.log_loss)}</td></tr>
      <tr><th>Brier score ↓</th><td>{fmt(model.brier_score)}</td><td>{fmt(prior.brier_score)}</td><td>{fmt(baseline.brier_score)}</td></tr>
      <tr><th>Most likely result correct</th><td>{fmt(model.accuracy*100,1)}%</td><td>{fmt(prior.accuracy*100,1)}%</td><td>{fmt(baseline.accuracy*100,1)}%</td></tr>
    </tbody></table></div>
    <p>The planning inputs have {fmt(Math.abs(delta))} {delta>=0?'lower':'higher'} log loss than the prior snapshot alone on this test. Lower log loss and Brier score are better; 0 is perfect. Accuracy splits credit when outcomes tie for most likely. The constant baseline uses training draw frequency and equal win/loss chances.</p>
    <h3>Win-chance calibration</h3><div className="quality-table"><table><thead><tr><th>Chance band</th><th>Team forecasts</th><th>Predicted wins</th><th>Actual wins</th></tr></thead><tbody>{model.win_calibration.map(row=><tr key={row.lower}><th>{row.lower*100}–{row.upper*100}%</th><td>{row.count.toLocaleString()}</td><td>{row.predicted_win_rate===null?'—':`${fmt(row.predicted_win_rate*100,1)}%`}</td><td>{row.actual_win_rate===null?'—':`${fmt(row.actual_win_rate*100,1)}%`}</td></tr>)}</tbody></table></div>
    <p>{test.excluded_games} games involving teams without prior ratings were excluded.</p><p>{test.scope}</p><p>{test.limitations}</p>
  </div></section>;
}
