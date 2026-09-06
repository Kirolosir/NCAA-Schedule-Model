'use client';
import { useEffect, useState } from 'react';
import { ArrowDownRight, ArrowUpRight, CircleHelp, MoveRight, Target } from 'lucide-react';
import { Slider } from '@/components/ui/slider';
import { Combobox, ComboboxContent, ComboboxEmpty, ComboboxInput, ComboboxItem, ComboboxList } from '@/components/ui/combobox';
import { api, Bootstrap, Config, Explore, fmt, Outcome, signed } from '@/lib/model';

export function Explorer({config,data,compact=false,initial=55}: {config:Config;data:Bootstrap;compact?:boolean;initial?:number}) {
  const [npi,setNpi]=useState(initial);
  const [named,setNamed]=useState<string|null>(null);
  const [result,setResult]=useState<Explore|null>(null);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(false);
  useEffect(()=>{const controller=new AbortController();setLoading(true);const timer=setTimeout(()=>api<Explore>('explore',{config,opponent_npi:npi},controller.signal).then(r=>{setResult(r);setError('');setLoading(false);}).catch(e=>{if(e.name!=='AbortError'){setError(e.message);setLoading(false);}}),150);return()=>{clearTimeout(timer);controller.abort();};},[npi,config]);
  const ratings=data.teams.map(t=>t.name).filter(t=>t!==config.target_team).sort();
  return <section className={`panel explorer-panel ${compact?'compact-explorer':''}`}>
    <div className="panel-heading"><div><p className="eyebrow">INSTANT WHAT-IF</p><h2>{compact?'What is one game worth?':'The shape of risk and reward.'}</h2></div><Target size={22}/></div>
    <div className="explorer-body">{!compact&&<div className="explorer-search"><label className="field">Use a real opponent<Combobox items={ratings} value={named} onValueChange={v=>{if(v){setNamed(String(v));setNpi(data.teams.find(t=>t.name===v)!.npi);}}}><ComboboxInput aria-label="Explore a named opponent" placeholder="Search all 407 team profiles…"/><ComboboxContent><ComboboxEmpty>No team found.</ComboboxEmpty><ComboboxList>{(name:string)=><ComboboxItem key={name} value={name}>{name}</ComboboxItem>}</ComboboxList></ComboboxContent></Combobox></label></div>}
      <div className="npi-input-line"><div><label htmlFor={compact?'quick-npi':'explore-npi'}>Opponent NPI rating</label><span>{named||'Adjust to explore a hypothetical opponent'}</span></div><input id={compact?'quick-npi':'explore-npi'} aria-label="Opponent NPI rating" type="number" value={npi} min={0} max={100} step={.1} onChange={e=>{const n=Number(e.target.value);if(Number.isFinite(n)&&n>=0&&n<=100){setNpi(n);setNamed(null);}}}/></div>
      <Slider aria-label="Opponent NPI rating slider" value={[Math.min(80,Math.max(30,npi))]} min={30} max={80} step={.1} onValueChange={v=>{setNpi(Array.isArray(v)?v[0]:v);setNamed(null);}}/><div className="slider-labels"><span>30 · Lower rating</span><span>80 · Higher rating</span></div>
      {npi>62.061&&<p className="field-note warning-text">Outside this export’s observed range. Arithmetic only; no matching historical profile.</p>}
      {error&&<div role="alert" className="notice error">{error}</div>}
      <div className={`outcome-tiles ${loading?'updating':''}`} aria-busy={loading}>{(['win','tie','loss'] as Outcome[]).filter(o=>!compact||o!=='tie').map(outcome=><div className={`outcome-tile ${outcome}`} key={outcome}><span>{outcome==='win'?<ArrowUpRight size={16}/>:outcome==='loss'?<ArrowDownRight size={16}/>:<MoveRight size={16}/>}If we {outcome}</span><strong>{signed(result?.outcomes[outcome].impact)}</strong><small>season NPI impact</small>{!compact&&<p>Season NPI <b>{fmt(result?.outcomes[outcome].npi)}</b></p>}</div>)}</div>
      {!compact&&result&&<div className="explorer-curve"><div className="chart-heading"><h3>One game, across the rating spectrum</h3><span className="chart-legend"><i className="legend-win"/>Win<i className="legend-tie"/>Tie<i className="legend-loss"/>Loss</span></div><Curve result={result} npi={npi}/><p className="field-note">Horizontal axis: opponent NPI. Vertical axis: season NPI change compared with omitting this game.</p></div>}
      {!compact&&result&&<div className="arithmetic-detail"><div><span>Win game value</span><strong>{fmt(result.outcomes.win.game_value?.total)}</strong></div><div><span>Quality-win bonus</span><strong>{fmt(result.outcomes.win.game_value?.quality_win_bonus)}</strong></div><div><span>Loss game value</span><strong>{fmt(result.outcomes.loss.game_value?.total)}</strong></div></div>}
    </div><div className="explorer-caveat"><CircleHelp size={16}/><p><strong>Instant arithmetic, not a division forecast.</strong> Other opponent ratings stay fixed; uncertain conference games use their most likely outcome. Use “Compare schedules” for full-division convergence.</p></div>
  </section>;
}

function Curve({result,npi}:{result:Explore;npi:number}) {
  const left=42,right=720,top=20,bottom=220;
  const values=result.curve.flatMap(r=>Object.values(r.outcomes).map(x=>x.impact));
  const lo=Math.floor(Math.min(...values,0)),hi=Math.ceil(Math.max(...values,1));
  const x=(n:number)=>left+(n-30)/50*(right-left),y=(v:number)=>bottom-(v-lo)/(hi-lo)*(bottom-top);
  return <svg viewBox="0 0 750 260" className="curve-svg" role="img" aria-label="Win, tie, and loss impact curves as opponent NPI rises from 30 to 80">
    {[lo,0,hi].filter((v,i,a)=>a.indexOf(v)===i).map(v=><g key={v}><line x1={left} x2={right} y1={y(v)} y2={y(v)} stroke={v===0?'#b5bbc9':'#edf0f5'} strokeDasharray={v===0?'5 4':undefined}/><text x={left-12} y={y(v)+4} textAnchor="end">{v>0?'+':''}{v}</text></g>)}
    {[30,40,50,60,70,80].map(v=><text key={v} x={x(v)} y={246} textAnchor="middle">{v}</text>)}
    {(['win','tie','loss'] as Outcome[]).map(o=><polyline key={o} fill="none" stroke={{win:'#328d75',tie:'#8a75ca',loss:'#cf7580'}[o]} strokeWidth="2.8" strokeLinejoin="round" points={result.curve.map(r=>`${x(r.npi)},${y(r.outcomes[o].impact)}`).join(' ')}/>)}
    {npi>=30&&npi<=80&&<><line x1={x(npi)} x2={x(npi)} y1={top} y2={bottom} stroke="#b9a5e9" strokeDasharray="4 4"/>{(['win','tie','loss'] as Outcome[]).map(o=><circle key={o} cx={x(npi)} cy={y(result.outcomes[o].impact)} r="4" fill={{win:'#328d75',tie:'#8a75ca',loss:'#cf7580'}[o]} stroke="white" strokeWidth="2"/>)}</>}
  </svg>;
}
