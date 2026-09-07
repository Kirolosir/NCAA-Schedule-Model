'use client';
import { useEffect, useState } from 'react';
import { ChevronDown, LockKeyhole, Pencil, Pin, Plus, RotateCcw, SlidersHorizontal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Combobox, ComboboxContent, ComboboxEmpty, ComboboxInput, ComboboxItem, ComboboxList } from '@/components/ui/combobox';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { api, Bootstrap, Candidate, Config, Explore, fmt, Outcome, Probabilities, Validation } from '@/lib/model';

export function Choice({label,value,options,onChange,disabled=false}: {label:string;value:string;options:{value:string;label:string}[];onChange:(v:string)=>void;disabled?:boolean}) {
  return <Select value={value} items={options} onValueChange={v=>v!==null&&onChange(String(v))} disabled={disabled}>
    <SelectTrigger aria-label={label} className="choice"><SelectValue/></SelectTrigger>
    <SelectContent>{options.map(o=><SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
  </Select>;
}

function CandidateEditor({candidate,data,config,onSave,onClose}: {candidate:Candidate;data:Bootstrap;config:Config;onSave:(c:Candidate)=>void;onClose:()=>void}) {
  const team=data.teams.find(t=>t.name===candidate.team)!;
  const [rating,setRating]=useState(String(candidate.recent_npi??team.npi));
  const [manual,setManual]=useState(!!candidate.probabilities);
  const [values,setValues]=useState(candidate.probabilities ? (['win','tie','loss'] as Outcome[]).map(o=>String(candidate.probabilities![o]*100)) : ['50','20','30']);
  const [predicted,setPredicted]=useState<Probabilities|null>(null);
  const [error,setError]=useState('');
  useEffect(()=>{
    const abort=new AbortController();
    if(rating===''||!Number.isFinite(Number(rating))||Number(rating)<0||Number(rating)>100) return;
    const timer=setTimeout(()=>api<Explore>('explore',{config,opponent_npi:Number(rating)},abort.signal).then(r=>{setPredicted(r.probabilities);setError('');}).catch(e=>{if(e.name!=='AbortError')setError(e.message);}),180);
    return()=>{clearTimeout(timer);abort.abort();};
  },[rating,config]);
  const total=values.reduce((sum,v)=>sum+Number(v),0);
  const valid=rating!==''&&Number.isFinite(Number(rating))&&Number(rating)>=0&&Number(rating)<=100&&(!manual||(values.every(v=>v!==''&&Number.isFinite(Number(v))&&Number(v)>=0&&Number(v)<=100)&&Math.abs(total-100)<1e-8));
  return <Dialog open onOpenChange={open=>!open&&onClose()}><DialogContent className="opponent-dialog"><DialogHeader><DialogTitle>{candidate.team}</DialogTitle><DialogDescription>Reference rank #{team.rank} · {team.record} · NPI {fmt(team.npi)}</DialogDescription></DialogHeader>
    <label className="field">Recent opponent NPI<input type="number" min="0" max="100" step="any" value={rating} onChange={e=>setRating(e.target.value)}/></label>
    <p className="field-note">Changes the pregame probabilities. The historical division graph still determines the converged rating.</p>
    <div className="switch-line"><label htmlFor="manual-probabilities">Set my own outcome probabilities</label><Switch id="manual-probabilities" checked={manual} onCheckedChange={checked=>{setManual(checked);if(checked&&!candidate.probabilities&&predicted){const w=Math.round(predicted.win*100),t=Math.round(predicted.tie*100);setValues([String(w),String(t),String(100-w-t)]);}}}/></div>
    <div className="probability-inputs">{(['win','tie','loss'] as Outcome[]).map((outcome,i)=><label className="field" key={outcome}>{outcome}<div className="suffix-input"><input aria-label={`${outcome} probability percent`} type="number" min="0" max="100" step="any" disabled={!manual} value={manual?values[i]:predicted?fmt(predicted[outcome]*100,1):''} onChange={e=>setValues(v=>v.map((x,j)=>j===i?e.target.value:x))}/><span>%</span></div></label>)}</div>
    <p className={manual&&Math.abs(total-100)>1e-8?'form-error':'field-note'}>{manual?`Total: ${fmt(total,1)}% · must equal 100%`:'Provisional historical model · not calibrated forecast probabilities.'}</p>
    {error&&<p className="form-error" role="alert">{error}</p>}
    <div className="dialog-actions"><Button variant="outline" onClick={onClose}>Cancel</Button><Button disabled={!valid} onClick={()=>onSave({team:candidate.team,recent_npi:Number(rating),...(manual?{probabilities:{win:Number(values[0])/100,tie:Number(values[1])/100,loss:Number(values[2])/100}}:{})})}>Apply changes</Button></div>
  </DialogContent></Dialog>;
}

export function Pool({data,config,validation,onChange,disabled}: {data:Bootstrap;config:Config;validation:Validation|null;onChange:(c:Config)=>void;disabled:boolean}) {
  const [editing,setEditing]=useState<Candidate|null>(null);
  const fixed=new Set(config.fixed_games.map(g=>g.team));
  const available=data.teams.map(t=>t.name).filter(t=>t!==config.target_team&&!fixed.has(t)&&!config.candidates.some(c=>c.team===t)).sort();
  const rows=[...(config.mode==='teams'?config.candidates:validation?.candidates||[])].sort((a,b)=>a.team.localeCompare(b.team));
  function toggle(team:string,on:boolean){onChange({...config,excluded:on?config.excluded.filter(t=>t!==team):[...new Set([...config.excluded,team])],required:on?config.required:config.required.filter(t=>t!==team)});}
  return <section className="panel pool-panel"><div className="panel-heading"><div><h2>Your opponent pool</h2><p>Select candidates. Pin must-play opponents.</p></div><span className="count-pill">{validation?.candidate_count??config.candidates.filter(c=>!config.excluded.includes(c.team)).length} available</span></div>
    <div className="pool-toolbar"><Tabs value={config.mode} onValueChange={v=>onChange({...config,mode:v as Config['mode'],required:[],excluded:[]})}><TabsList><TabsTrigger value="teams" disabled={disabled}>Specific teams</TabsTrigger><TabsTrigger value="bands" disabled={disabled}>Opponent bands</TabsTrigger></TabsList></Tabs>
      {config.mode==='bands'&&<Choice label="Band scale" value={config.band_scale} disabled={disabled} onChange={v=>onChange({...config,band_scale:v as Config['band_scale'],required:[]})} options={[{value:'rating',label:'NPI ratings'},{value:'rank',label:'Rank positions'}]}/>}</div>
    {config.mode==='teams'?<div className="add-opponent"><Plus size={16}/><Combobox items={available} value={null} onValueChange={name=>name&&onChange({...config,candidates:[...config.candidates,{team:String(name)}]})} disabled={disabled}><ComboboxInput aria-label="Find an opponent to add" placeholder="Find a team to add…" className="team-search"/><ComboboxContent><ComboboxEmpty>No available teams found.</ComboboxEmpty><ComboboxList>{(name:string)=><ComboboxItem key={name} value={name}>{name}</ComboboxItem>}</ComboboxList></ComboboxContent></Combobox></div>:
      <div className="band-controls"><div className="band-chips">{data.config.bands.map(b=>{const active=config.bands.some(x=>x.label===b.label);return <label className={`band-chip ${active?'active':''}`} key={b.label}><Checkbox checked={active} disabled={disabled} aria-label={`${b.label} band`} onCheckedChange={on=>onChange({...config,bands:on?[...config.bands,b]:config.bands.filter(x=>x.label!==b.label),required:[]})}/>{b.label}</label>;})}</div><p className="field-note">{config.band_scale==='rating'?`Actual ratings span ${fmt(data.rating_range[0])}–${fmt(data.rating_range[1])}. Other rating bands have no historical profiles.`:'Lower rank positions are stronger. Bands include their lower boundary, not their upper.'}</p><div className="inline-setting"><span>Profiles per band</span><Choice label="Representatives per band" value={String(config.representatives_per_band)} disabled={disabled} options={[1,2,3,4,5].map(n=>({value:String(n),label:String(n)}))} onChange={v=>onChange({...config,representatives_per_band:Number(v),required:[]})}/></div></div>}
    <div className="pool-list">{rows.map((c,i)=>{const team=data.teams.find(t=>t.name===c.team)!;const included=!config.excluded.includes(c.team),pinned=config.required.includes(c.team);return <div className={`pool-row ${included?'':'excluded'}`} key={c.team}>
      {config.mode==='teams'&&<Checkbox checked={included} disabled={disabled} aria-label={`Include ${c.team}`} onCheckedChange={on=>toggle(c.team,on)}/>}
      <span className={`team-avatar tint-${i%4}`}>{c.team.split(' ').map(x=>x[0]).slice(0,2).join('')}</span><button className="team-name team-edit" disabled={disabled||config.mode==='bands'} onClick={()=>setEditing(c)}><strong>{c.team}</strong><span>#{team.rank} <span className="sep">·</span> {team.record}{c.probabilities?' · Custom odds':''}</span></button>
      <div className="rating"><strong>{fmt(c.recent_npi??team.npi)}</strong><span>{c.recent_npi!==undefined&&c.recent_npi!==team.npi?'RECENT NPI':'NPI RATING'}</span></div>
      <Button variant="ghost" size="icon" className={`pin-button ${pinned?'pinned':''}`} disabled={disabled||!included} aria-label={`${pinned?'Unpin':'Require'} ${c.team}`} aria-pressed={pinned} onClick={()=>onChange({...config,required:pinned?config.required.filter(t=>t!==c.team):[...config.required,c.team]})}><Pin size={16}/></Button>
    </div>;})}{!rows.length&&<div className="empty-state">No profiles in this pool yet. Add a team or choose a populated band.</div>}</div>
    <div className="panel-foot">{config.mode==='teams'?<><Pencil size={14}/>Click a team to adjust its NPI or win/tie/loss odds.</>:<>Real representative profiles, not a band-wide average.</>}</div>
    {editing&&<CandidateEditor key={editing.team} candidate={editing} data={data} config={config} onClose={()=>setEditing(null)} onSave={updated=>{onChange({...config,candidates:config.candidates.map(c=>c.team===updated.team?updated:c)});setEditing(null);}}/>}
  </section>;
}

export function Settings({config,onChange,onReset,disabled}: {config:Config;onChange:(c:Config)=>void;onReset:()=>void;disabled:boolean}) {
  const effort=config.samples===4?'quick':config.samples===12?'balanced':config.samples===24?'detailed':'custom';
  return <section className="panel settings-panel"><div className="panel-heading"><h2>Plan settings</h2><SlidersHorizontal size={18}/></div><div className="settings-body">
    <label className="field">Outcome probability model<Choice label="Outcome probability model" value={config.probability_model} disabled={disabled||!['2024','2025'].includes(config.season)} onChange={v=>onChange({...config,probability_model:v as Config['probability_model'],probability_slope_scale:v==='historical'?1:.5})} options={['2024','2025'].includes(config.season)?[{value:'historical',label:'Prior-season fit'},{value:'retrospective',label:'Same-season replay'}]:[{value:'retrospective',label:'Same-season replay'}]}/></label>
    <div className="inline-setting"><label>Open nonconference slots</label><Choice label="Open nonconference slots" value={String(config.open_slots)} disabled={disabled} onChange={v=>onChange({...config,open_slots:Number(v)})} options={[1,2,3,4,5,6,7,8].map(n=>({value:String(n),label:String(n)}))}/></div>
    <label className="field">Simulation detail<Choice label="Simulation detail" value={effort} disabled={disabled} onChange={v=>{const presets:Record<string,number[]>={quick:[4,8,2],balanced:[12,32,4],detailed:[24,64,8]};const p=presets[v];if(p)onChange({...config,samples:p[0],validation_samples:p[1],insight_samples:p[2]});}} options={[{value:'quick',label:'Quick exploration'},{value:'balanced',label:'Balanced'},{value:'detailed',label:'Detailed comparison'},...(effort==='custom'?[{value:'custom',label:'Custom settings'}]:[])]}/></label>
    <p className="field-note">{config.samples} screening draws · {config.validation_samples} validation draws. Detailed runs can take several minutes.</p>
    <div className="slider-heading"><label id="strength-label">Strength sensitivity</label><strong>{fmt(config.probability_slope_scale,2)}×</strong></div><Slider aria-labelledby="strength-label" value={[config.probability_slope_scale]} min={.25} max={1.5} step={.05} disabled={disabled} onValueChange={v=>onChange({...config,probability_slope_scale:Array.isArray(v)?v[0]:v})}/><div className="slider-labels"><span>More uncertain</span><span>Stronger favorites</span></div>
    <p className="field-note">1.0× uses the selected fit directly. Lower values soften the gap between favorites and underdogs.</p>
    <Button variant="ghost" className="reset-button" disabled={disabled} onClick={onReset}><RotateCcw size={14}/>Reset to reference inputs</Button>
  </div></section>;
}

export function Conference({config,onChange,disabled}: {config:Config;onChange:(c:Config)=>void;disabled:boolean}) {
  return <details className="panel conference-panel"><summary><span><LockKeyhole size={17}/><strong>Fixed conference slate</strong><span className="count-pill">{config.fixed_games.length} games</span></span><ChevronDown size={17}/></summary><div className="conference-list"><p>Lock a known result, or leave it uncertain for planning.</p>{config.fixed_games.map((game,i)=><div className="conference-row" key={game.team}><span>{game.team}</span><Choice label={`${game.team} outcome`} value={game.result||'uncertain'} disabled={disabled} options={[{value:'uncertain',label:'Uncertain'},{value:'win',label:'Win'},{value:'tie',label:'Tie'},{value:'loss',label:'Loss'}]} onChange={v=>onChange({...config,fixed_games:config.fixed_games.map((g,j)=>{if(i!==j)return g;const {result:_old,probabilities:_p,...rest}=g;return {...rest,...(v==='uncertain'?{}:{result:v as Outcome})};})})}/></div>)}</div></details>;
}
