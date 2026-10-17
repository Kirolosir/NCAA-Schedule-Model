import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { api, fmt, Report, SensitivityReport, Summary } from '@/lib/model';

type AnalysisJob = {id:string;status:string;message:string;report?:SensitivityReport};

export function SensitivityPanel({report,onComplete}:{report:Report;onComplete:(result:SensitivityReport|null)=>void}) {
  const [shift,setShift]=useState('3');
  const [result,setResult]=useState<SensitivityReport|null>(null);
  const [message,setMessage]=useState('');
  const [busy,setBusy]=useState(false);
  const active=useRef<string|null>(null);
  const generation=useRef(0);
  const timer=useRef<ReturnType<typeof setTimeout>|null>(null);
  useEffect(()=>{
    generation.current++;setResult(null);setMessage('');setBusy(false);onComplete(null);
    return()=>{generation.current++;if(timer.current)clearTimeout(timer.current);const id=active.current;active.current=null;if(id)void api(`jobs/${id}/cancel`,{}).catch(()=>{});};
  },[report,onComplete]);
  const valid=shift!==''&&Number.isFinite(Number(shift))&&Number(shift)>=.25&&Number(shift)<=10;
  async function run(){
    if(!valid||busy)return;
    const requestGeneration=++generation.current;
    setBusy(true);setMessage('Preparing the same options under three assumptions…');setResult(null);onComplete(null);
    try{
      const created=await api<{id:string}>('sensitivity-jobs',{config:report.config,schedules:report.top_schedules.map(row=>row.opponents),strength_shift:Number(shift)});
      if(requestGeneration!==generation.current){void api(`jobs/${created.id}/cancel`,{}).catch(()=>{});return;}
      active.current=created.id;
      const poll=async()=>{
        try{
          const job=await api<AnalysisJob>(`jobs/${created.id}`);
          if(requestGeneration!==generation.current)return;
          setMessage(job.message);
          if(job.status==='complete'&&job.report){active.current=null;setResult(job.report);onComplete(job.report);setBusy(false);}
          else if(['error','cancelled'].includes(job.status)){active.current=null;setBusy(false);}
          else timer.current=setTimeout(poll,700);
        }catch(error){if(requestGeneration===generation.current){setBusy(false);setMessage((error as Error).message);const id=active.current;active.current=null;if(id)void api(`jobs/${id}/cancel`,{}).catch(()=>{});}}
      };
      timer.current=setTimeout(poll,200);
    }catch(error){if(requestGeneration===generation.current){setBusy(false);setMessage((error as Error).message);}}
  }
  function cancel(){generation.current++;if(timer.current)clearTimeout(timer.current);const id=active.current;active.current=null;setBusy(false);setMessage('Sensitivity comparison cancelled.');if(id)void api(`jobs/${id}/cancel`,{}).catch(()=>{});}
  const interval=(gap:Summary)=>gap.mean_ci95[0]<=0?'Close to the leader':`${fmt(gap.mean)} below leader`;
  return <section className="panel sensitivity-panel"><div className="panel-heading"><div><h2>Does the recommendation hold up?</h2><p>Compare these same {report.top_schedules.length} options under lower, entered, and higher team form.</p></div></div><div className="sensitivity-body">
    <div className="sensitivity-actions"><label className="field">Team-strength change (NPI points)<input aria-label="Sensitivity strength change" type="number" min=".25" max="10" step=".25" disabled={busy} value={shift} onChange={event=>setShift(event.target.value)}/></label><Button disabled={busy||!valid} onClick={run}>{result?'Run again':'Compare assumptions'}</Button>{busy&&<Button variant="outline" onClick={cancel}>Cancel</Button>}</div>
    <p className="field-note">Only model-derived matchup chances change. Your locked results and entered percentages stay fixed. The form shift does not edit ratings or completed games in your setup.</p>
    {message&&<p role="status" className="field-note">{message}</p>}
    {result&&<>
      <div className="quality-table"><table><thead><tr><th>Option</th>{result.profiles.map(profile=><th key={profile.key}>{profile.label}<small>{profile.effective_shift>=0?'+':''}{fmt(profile.effective_shift,1)} strength</small></th>)}<th>Largest gap to a leader</th></tr></thead><tbody>{result.schedules.map(row=><tr key={row.option}><th>Option {row.option}<small>{row.opponents.join(', ')}</small></th>{result.profiles.map(profile=>{const value=profile.schedules.find(item=>item.option===row.option)!;return <td key={profile.key}><strong>{fmt(value.projection.mean)}</strong><small>{fmt(value.target_hit_rate*100,0)}% reach target · rank {value.rank}</small><small>{interval(value.gap_from_leader)}</small></td>;})}<td>{fmt(row.largest_gap_to_leader)}<small>Estimated NPI gap</small></td></tr>)}</tbody></table></div>
      <p><strong>Option {result.most_consistent_option} has the smallest worst-case estimated gap to a leader on this shortlist.</strong> Close options may swap rank with more samples. This comparison uses {result.samples_per_profile} samples per profile and {result.division_solves} full-division calculations.</p>
      <p className="field-note">{result.scope}</p><p className="field-note">{result.note}</p>
      {Number(shift)!==result.strength_shift&&<p className="field-note">The table uses ±{result.strength_shift} points. Run again to apply the changed input.</p>}
    </>}
  </div></section>;
}
