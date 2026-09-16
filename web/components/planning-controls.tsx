'use client';
import { useEffect, useState } from 'react';
import { CalendarDays, Check, ChevronDown, DollarSign, LockKeyhole, MapPin, Pencil, Pin, Plus, RefreshCw, RotateCcw, SlidersHorizontal, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Combobox, ComboboxContent, ComboboxEmpty, ComboboxInput, ComboboxItem, ComboboxList } from '@/components/ui/combobox';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { api, Bootstrap, Candidate, Config, Explore, fmt, Matchup, NescacSync, Outcome, Priority, Probabilities, Validation, Venue } from '@/lib/model';

const PRESETS: Record<'favorite'|'toss_up'|'underdog', Probabilities> = {
  favorite: {win:.65,tie:.20,loss:.15},
  toss_up: {win:.40,tie:.20,loss:.40},
  underdog: {win:.15,tie:.20,loss:.65},
};
const OUTLOOK_LABEL={favorite:'Amherst favored',toss_up:'Toss-up',underdog:'Amherst underdog'} as const;
const EFFORT_OPTIONS=[
  {key:'quick',label:'Quick',note:'Best while you are still trying ideas and swapping teams.',time:'~20 sec'},
  {key:'standard',label:'Standard',note:'A larger sample and a longer shortlist of finalists.',time:'~2 min'},
  {key:'thorough',label:'Thorough',note:'Use this once, on the final few options, before you commit.',time:'~8 min'},
] as const;
const FINISH_PRESETS=[
  {key:'cautious',eyebrow:'CAUTIOUS',ratios:[.3,.2,.5] as [number,number,number],note:'Plan as if the conference goes against you. The safest number to bring to a budget meeting.'},
  {key:'baseline',eyebrow:'COACH’S BASELINE',ratios:[.4,.2,.4] as [number,number,number],note:'Beat the lowest-NPI teams, tie the middle, and lose to the highest-NPI teams.'},
  {key:'optimistic',eyebrow:'OPTIMISTIC',ratios:[.6,.2,.2] as [number,number,number],note:'A strong conference year. Useful for seeing how much the nonconference slate still matters.'},
];
function scaleFinish(ratios:[number,number,number],total:number):[number,number,number]{
  const raw=ratios.map(r=>r*total);
  const floors=raw.map(Math.floor);
  const remainder=total-floors.reduce((sum,value)=>sum+value,0);
  const order=raw.map((value,i)=>({i,frac:value-floors[i]})).sort((a,b)=>b.frac-a.frac);
  const result=[...floors] as [number,number,number];
  for(let k=0;k<remainder;k++)result[order[k].i]++;
  return result;
}

export function Choice({label,value,options,onChange,disabled=false}: {label:string;value:string;options:{value:string;label:string}[];onChange:(v:string)=>void;disabled?:boolean}) {
  return <Select value={value} items={options} onValueChange={v=>v!==null&&onChange(String(v))} disabled={disabled}>
    <SelectTrigger aria-label={label} className="choice"><SelectValue/></SelectTrigger>
    <SelectContent>{options.map(o=><SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
  </Select>;
}

function SegmentedChoice({label,value,options,onChange}: {label:string;value:string;options:{value:string;label:string}[];onChange:(v:string)=>void}) {
  return <div className="segmented-choice" role="group" aria-label={label}>{options.map(option=><button type="button" key={option.value} aria-pressed={value===option.value} onClick={()=>onChange(option.value)}>{option.label}</button>)}</div>;
}

function CandidateEditor({candidate,status,data,config,onSave,onClose}: {candidate:Candidate;status:Priority|'unavailable';data:Bootstrap;config:Config;onSave:(c:Candidate,status:Priority|'unavailable')=>void;onClose:()=>void}) {
  const team=data.teams.find(t=>t.name===candidate.team)!;
  const [rating,setRating]=useState(String(candidate.recent_npi??team.planning_npi));
  const [matchup,setMatchup]=useState<Matchup>(candidate.matchup??(candidate.probabilities?'custom':'model'));
  const [values,setValues]=useState(candidate.probabilities ? (['win','tie','loss'] as Outcome[]).map(o=>String(candidate.probabilities![o]*100)) : ['50','20','30']);
  const [priority,setPriority]=useState(status);
  const [venue,setVenue]=useState<Venue>(candidate.venue??'either');
  const [dates,setDates]=useState<string[]>(candidate.available_dates??[]);
  const [restrictDates,setRestrictDates]=useState(Boolean(candidate.available_dates?.length));
  const [newDate,setNewDate]=useState('');
  const [travel,setTravel]=useState(String(candidate.travel_miles??0));
  const [cost,setCost]=useState(String(candidate.estimated_cost??0));
  const [predicted,setPredicted]=useState<Probabilities|null>(null);
  const [error,setError]=useState('');
  useEffect(()=>{
    const abort=new AbortController();
    if(rating===''||!Number.isFinite(Number(rating))||Number(rating)<0||Number(rating)>100)return;
    const timer=setTimeout(()=>api<Explore>('explore',{config,opponent_npi:Number(rating)},abort.signal).then(r=>{setPredicted(r.probabilities);setError('');}).catch(e=>{if(e.name!=='AbortError')setError(e.message);}),180);
    return()=>{clearTimeout(timer);abort.abort();};
  },[rating,config]);
  const selected=matchup==='model'?predicted:matchup==='custom'?{
    win:Number(values[0])/100,tie:Number(values[1])/100,loss:Number(values[2])/100,
  }:PRESETS[matchup];
  const total=values.reduce((sum,v)=>sum+Number(v),0);
  const valid=rating!==''&&Number.isFinite(Number(rating))&&Number(rating)>=0&&Number(rating)<=100&&
    travel!==''&&Number.isFinite(Number(travel))&&Number(travel)>=0&&cost!==''&&Number.isFinite(Number(cost))&&Number(cost)>=0&&(!restrictDates||dates.length>0)&&
    (matchup!=='custom'||(values.every(v=>v!==''&&Number.isFinite(Number(v))&&Number(v)>=0&&Number(v)<=100)&&Math.abs(total-100)<1e-8));
  function save(){
    if(!valid)return;
    onSave({team:candidate.team,recent_npi:Number(rating),matchup,venue,available_dates:restrictDates?dates:[],
      travel_miles:Number(travel),estimated_cost:Number(cost),...(matchup==='model'?{}:{probabilities:selected!})},priority);
  }
  return <Dialog open onOpenChange={open=>!open&&onClose()}><DialogContent className="opponent-dialog"><DialogHeader><DialogTitle>{candidate.team}</DialogTitle><DialogDescription>2025 reference: national rank #{team.rank} · {team.record} · NPI {fmt(team.npi)} · three-season strength {fmt(team.planning_npi)}</DialogDescription></DialogHeader>
    <div className="editor-sections"><section><h3>Matchup outlook</h3><div className="model-start"><strong>Three-season starting point: {OUTLOOK_LABEL[team.matchup_outlook]}</strong><span>{fmt(team.matchup_probabilities.win*100,0)}% win · {fmt(team.matchup_probabilities.tie*100,0)}% tie · {fmt(team.matchup_probabilities.loss*100,0)}% loss</span></div><div className="planning-fields"><label className="field">Planning strength<input type="number" min="0" max="100" step="any" value={rating} onChange={e=>setRating(e.target.value)}/></label><label className="field">Expected matchup<Choice label="Expected matchup" value={matchup} onChange={v=>setMatchup(v as Matchup)} options={[{value:'model',label:'Use historical model'},{value:'favorite',label:'Amherst favored'},{value:'toss_up',label:'Toss-up'},{value:'underdog',label:'Amherst underdog'},{value:'custom',label:'Set exact chances'}]}/></label></div>
      <div className="probability-inputs">{(['win','tie','loss'] as Outcome[]).map((outcome,i)=><label className="field" key={outcome}>{outcome}<div className="suffix-input"><input aria-label={`${outcome} probability percent`} type="number" min="0" max="100" step="any" disabled={matchup!=='custom'} value={matchup==='custom'?values[i]:selected?fmt(selected[outcome]*100,0):''} onChange={e=>setValues(v=>v.map((x,j)=>j===i?e.target.value:x))}/><span>%</span></div></label>)}</div>
      <p className={matchup==='custom'&&Math.abs(total-100)>1e-8?'form-error':'field-note'}>{matchup==='custom'?`Total: ${fmt(total,1)}% · must equal 100%`:'The preset changes outcome chances. Venue and travel remain visible planning details.'}</p></section>
      <section><h3>Practical planning</h3><label className="field">Scheduling status<Choice label="Scheduling status" value={priority} onChange={v=>setPriority(v as Priority|'unavailable')} options={[{value:'available',label:'Available'},{value:'preferred',label:'Preferred'},{value:'required',label:'Required'},{value:'unavailable',label:'Unavailable'}]}/></label><div className="field venue-field"><span>Home or away possibilities</span><SegmentedChoice label="Home or away possibilities" value={venue} onChange={v=>setVenue(v as Venue)} options={[{value:'either',label:'Either'},{value:'home',label:'Home'},{value:'away',label:'Away'}]}/></div>
      <div className="date-toggle"><div><strong>Limit to available dates</strong><span>Turn this on to enter the dates this opponent can play.</span></div><Switch checked={restrictDates} onCheckedChange={setRestrictDates} aria-label="Limit to available dates"/></div>
      {restrictDates&&<><label className="field">Available dates<div className="date-entry"><input aria-label="Add available date" type="date" value={newDate} onChange={e=>setNewDate(e.target.value)}/><Button type="button" variant="outline" disabled={!newDate||dates.includes(newDate)} onClick={()=>{setDates([...dates,newDate].sort());setNewDate('');}}><Plus size={15}/>Add date</Button></div></label><div className="date-chips">{dates.map(day=><span key={day}><CalendarDays size={13}/>{new Date(`${day}T12:00:00`).toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'})}<button aria-label={`Remove ${day}`} onClick={()=>setDates(dates.filter(x=>x!==day))}><X size={12}/></button></span>)}{!dates.length&&<em>Add at least one available date</em>}</div></>}
      <div className="planning-fields"><label className="field"><span className="field-with-icon"><MapPin size={14}/>Round-trip travel miles</span><input type="number" min="0" step="1" value={travel} onChange={e=>setTravel(e.target.value)}/></label><label className="field"><span className="field-with-icon"><DollarSign size={14}/>Estimated cost</span><input type="number" min="0" step="100" value={cost} onChange={e=>setCost(e.target.value)}/></label></div></section></div>
    {error&&<p className="form-error" role="alert">{error}</p>}
    <div className="dialog-actions"><Button variant="outline" onClick={onClose}>Cancel</Button><Button disabled={!valid} onClick={save}>Apply changes</Button></div>
  </DialogContent></Dialog>;
}

export function Pool({data,config,validation,onChange,disabled}: {data:Bootstrap;config:Config;validation:Validation|null;onChange:(c:Config)=>void;disabled:boolean}) {
  const [editing,setEditing]=useState<Candidate|null>(null);
  const fixed=new Set(config.fixed_games.map(g=>g.team));
  const available=data.teams.map(t=>t.name).filter(t=>t!==config.target_team&&!fixed.has(t)&&!config.candidates.some(c=>c.team===t)).sort();
  const rows=[...(config.mode==='teams'?config.candidates:validation?.candidates||[])].sort((a,b)=>a.team.localeCompare(b.team));
  function status(team:string):Priority|'unavailable'{return config.excluded.includes(team)?'unavailable':config.required.includes(team)?'required':config.preferred.includes(team)?'preferred':'available';}
  function setStatus(team:string,next:Priority|'unavailable',base=config){onChange({...base,required:next==='required'?[...new Set([...base.required,team])]:base.required.filter(t=>t!==team),preferred:next==='preferred'?[...new Set([...base.preferred,team])]:base.preferred.filter(t=>t!==team),excluded:next==='unavailable'?[...new Set([...base.excluded,team])]:base.excluded.filter(t=>t!==team)});}
  function toggle(team:string,on:boolean){setStatus(team,on?'available':'unavailable');}
  return <section className="panel pool-panel"><div className="panel-heading"><div><h2>Possible nonconference opponents</h2><p>Add realistic teams, then open each one to set matchup and travel details.</p></div><span className="count-pill">{validation?.candidate_count??config.candidates.filter(c=>!config.excluded.includes(c.team)).length} in pool</span></div>
    <div className="pool-toolbar"><Tabs value={config.mode} onValueChange={v=>onChange({...config,mode:v as Config['mode'],required:[],preferred:[],excluded:[]})}><TabsList><TabsTrigger value="teams" disabled={disabled}>Choose teams</TabsTrigger><TabsTrigger value="bands" disabled={disabled}>Use strength bands</TabsTrigger></TabsList></Tabs>{config.mode==='bands'&&<Choice label="Band scale" value={config.band_scale} disabled={disabled} onChange={v=>onChange({...config,band_scale:v as Config['band_scale'],required:[],preferred:[]})} options={[{value:'rating',label:'NPI ratings'},{value:'rank',label:'Rank positions'}]}/>}</div>
    {config.mode==='teams'?<div className="add-opponent"><Plus size={16}/><Combobox items={available} value={null} onValueChange={name=>{if(!name)return;const team=data.teams.find(t=>t.name===String(name))!;onChange({...config,candidates:[...config.candidates,{team:String(name),recent_npi:team.planning_npi,matchup:'model',venue:'either',available_dates:[],travel_miles:0,estimated_cost:0}]});}} disabled={disabled}><ComboboxInput aria-label="Find an opponent to add" placeholder="Find a team to add…" className="team-search"/><ComboboxContent><ComboboxEmpty>No available teams found.</ComboboxEmpty><ComboboxList>{(name:string)=><ComboboxItem key={name} value={name}>{name}</ComboboxItem>}</ComboboxList></ComboboxContent></Combobox></div>:<div className="band-controls"><div className="band-chips">{data.config.bands.map(b=>{const active=config.bands.some(x=>x.label===b.label);return <label className={`band-chip ${active?'active':''}`} key={b.label}><Checkbox checked={active} disabled={disabled} aria-label={`${b.label} band`} onCheckedChange={on=>onChange({...config,bands:on?[...config.bands,b]:config.bands.filter(x=>x.label!==b.label),required:[],preferred:[]})}/>{b.label}</label>;})}</div><p className="field-note">{config.band_scale==='rating'?`Actual ratings span ${fmt(data.rating_range[0])}–${fmt(data.rating_range[1])}. Other rating bands have no historical profiles.`:'Lower rank positions are stronger. Bands include their lower boundary, not their upper.'}</p><div className="inline-setting"><span>Profiles per band</span><Choice label="Representatives per band" value={String(config.representatives_per_band)} disabled={disabled} options={[1,2,3,4,5].map(n=>({value:String(n),label:String(n)}))} onChange={v=>onChange({...config,representatives_per_band:Number(v),required:[],preferred:[]})}/></div></div>}
    <div className="pool-list">{rows.map((c,i)=>{const team=data.teams.find(t=>t.name===c.team)!;const state=status(c.team),included=state!=='unavailable';return <div className={`pool-row ${included?'':'excluded'}`} key={c.team}>{config.mode==='teams'&&<Checkbox checked={included} disabled={disabled} aria-label={`Include ${c.team}`} onCheckedChange={on=>toggle(c.team,on)}/>}<span className={`team-avatar tint-${i%4}`}>{c.team.split(' ').map(x=>x[0]).slice(0,2).join('')}</span><button className="team-name team-edit" disabled={disabled||config.mode==='bands'} onClick={()=>setEditing(c)}><strong>{c.team}</strong><span>#{team.rank} <span className="sep">·</span> {team.record} <span className={`status-pill ${state}`}>{state}</span></span><span className="row-meta">{c.matchup&&c.matchup!=='model'?c.matchup.replace('_',' '):`Model: ${OUTLOOK_LABEL[team.matchup_outlook]}`} · {c.venue==='home'?'Home':c.venue==='away'?'Away':'Venue open'}{c.available_dates?.length?` · ${c.available_dates.length} date${c.available_dates.length===1?'':'s'}`:''}{c.travel_miles?` · ${c.travel_miles.toLocaleString()} mi`:''}{c.estimated_cost?` · $${c.estimated_cost.toLocaleString()}`:''}</span></button><div className="rating"><strong>{fmt(c.recent_npi??team.planning_npi)}</strong><span>3-SEASON FORM</span></div><Button variant="ghost" size="icon" className={`pin-button ${state==='required'?'pinned':''}`} disabled={disabled||!included} aria-label={`${state==='required'?'Make available':'Require'} ${c.team}`} aria-pressed={state==='required'} onClick={()=>setStatus(c.team,state==='required'?'available':'required')}><Pin size={16}/></Button></div>;})}{!rows.length&&<div className="empty-state">No profiles in this pool yet. Add a team or choose a populated band.</div>}</div>
    <div className="panel-foot">{config.mode==='teams'?<><Pencil size={14}/>Click a team to set status, matchup, venue, dates, travel, and cost.</>:<>Each band uses real historical teams as examples instead of one imaginary average team.</>}</div>
    {editing&&<CandidateEditor key={editing.team} candidate={editing} status={status(editing.team)} data={data} config={config} onClose={()=>setEditing(null)} onSave={(updated,next)=>{const nextConfig={...config,candidates:config.candidates.map(c=>c.team===updated.team?updated:c)};setEditing(null);setStatus(updated.team,next,nextConfig);}}/>}
  </section>;
}

export function Settings({config,onChange,onReset,disabled}: {config:Config;onChange:(c:Config)=>void;onReset:()=>void;disabled:boolean}) {
  const effort=config.analysis_mode;
  function optionalNumber(key:'max_total_travel_miles'|'max_total_cost',value:string){onChange({...config,[key]:value===''?null:Number(value)});}
  function applyEffort(key:string){const presets:Record<string,[number,number,number,number]>={quick:[4,4,2,1e-6],standard:[8,8,4,1e-7],thorough:[24,64,8,1e-8]};const p=presets[key];if(p)onChange({...config,analysis_mode:key as Config['analysis_mode'],samples:p[0],validation_samples:p[1],insight_samples:p[2],convergence_tolerance:p[3]});}
  return <section className="panel settings-panel"><div className="panel-heading"><h2>Comparison setup</h2><SlidersHorizontal size={18}/></div><div className="settings-body">
    <div className="limit-section"><h3>Travel and cost limits</h3><div className="planning-fields limit-fields"><label className="field"><span className="field-with-icon"><MapPin size={14}/>Maximum travel miles</span><input type="number" min="0" placeholder="No limit" disabled={disabled} value={config.max_total_travel_miles??''} onChange={e=>optionalNumber('max_total_travel_miles',e.target.value)}/></label><label className="field"><span className="field-with-icon"><DollarSign size={14}/>Maximum total cost</span><input type="number" min="0" placeholder="No limit" disabled={disabled} value={config.max_total_cost??''} onChange={e=>optionalNumber('max_total_cost',e.target.value)}/></label></div><p className="field-note">Schedules above either limit are removed. Leave a field blank when there is no limit.</p>
      <div className="limit-slots"><div><strong>Nonconference games to choose</strong><span>Five is the standard NESCAC allowance.</span></div><div className="slot-picker">{[1,2,3,4,5,6,7,8].map(n=><button type="button" key={n} className={config.open_slots===n?'on':''} disabled={disabled} onClick={()=>onChange({...config,open_slots:n})}>{n}</button>)}</div></div>
    </div>
    <div className="field"><label>How carefully should we check?</label><div className="effort-cards">{EFFORT_OPTIONS.map(option=>{const on=effort===option.key;return <button type="button" key={option.key} className={`effort-card ${on?'on':''}`} disabled={disabled} onClick={()=>applyEffort(option.key)}><span className="effort-ring"><span/></span><span style={{minWidth:0,flex:1}}><strong>{option.label}</strong><span className="effort-note">{option.note}</span></span><span className="effort-time">{option.time}</span></button>;})}</div></div>
    <details className="advanced-settings"><summary><span>Advanced assumptions</span><ChevronDown size={16}/></summary><div><label className="field">How to estimate game outcomes<Choice label="How to estimate game outcomes" value={config.probability_model} disabled={disabled||!['2024','2025'].includes(config.season)} onChange={v=>onChange({...config,probability_model:v as Config['probability_model'],probability_slope_scale:v==='historical'?1:.5})} options={['2024','2025'].includes(config.season)?[{value:'historical',label:'Use earlier seasons'},{value:'retrospective',label:'Replay this season'}]:[{value:'retrospective',label:'Replay this season'}]}/></label><div className="slider-heading"><label id="strength-label">How much to trust the NPI gap</label><strong>{fmt(config.probability_slope_scale,2)}×</strong></div><Slider aria-labelledby="strength-label" value={[config.probability_slope_scale]} min={.25} max={1.5} step={.05} disabled={disabled} onValueChange={v=>onChange({...config,probability_slope_scale:Array.isArray(v)?v[0]:v})}/><div className="slider-labels"><span>Games are less predictable</span><span>Favorites win more often</span></div><p className="field-note">1.0× follows the historical relationship. Lower values treat more games as toss-ups.</p></div></details><Button variant="ghost" className="reset-button" disabled={disabled} onClick={onReset}><RotateCcw size={14}/>Reset to reference inputs</Button></div></section>;
}

export function SeasonRecord({config,data,onChange,disabled,expanded=false}: {config:Config;data:Bootstrap;onChange:(c:Config)=>void;disabled:boolean;expanded?:boolean}) {
  const completed=config.fixed_games.filter(game=>game.completed);
  const counts=(['win','tie','loss'] as Outcome[]).map(outcome=>completed.filter(game=>game.result===outcome).length);
  const available=data.teams.map(team=>team.name).filter(team=>team!==config.target_team&&!completed.some(game=>game.team===team)).sort();
  const [sync,setSync]=useState<NescacSync|null>(null);
  const [syncing,setSyncing]=useState(false);
  const [dismissed,setDismissed]=useState<Set<string>>(new Set());
  async function checkForResults(){
    setSyncing(true);
    try{setSync(await api<NescacSync>('nescac-results'));}
    catch(error){setSync({results:[],source:null,error:(error as Error).message});}
    finally{setSyncing(false);}
  }
  const pending=(sync?.results??[]).filter(item=>{
    const game=config.fixed_games.find(g=>g.team===item.team);
    return game&&!game.completed&&!dismissed.has(item.team);
  });
  function add(team:string){const existing=config.fixed_games.find(game=>game.team===team);const fixed=existing?config.fixed_games.map(game=>{if(game.team!==team)return game;const {probabilities:_p,decision:_d,...rest}=game;return {...rest,result:'win' as Outcome,completed:true};}):[...config.fixed_games,{team,category:'nonconference',result:'win' as Outcome,completed:true}];onChange({...config,fixed_games:fixed,candidates:config.candidates.filter(candidate=>candidate.team!==team),required:config.required.filter(name=>name!==team),preferred:config.preferred.filter(name=>name!==team),excluded:config.excluded.filter(name=>name!==team)});}
  function setOutcome(team:string,value:string){onChange({...config,fixed_games:config.fixed_games.map(game=>{if(game.team!==team)return game;const {probabilities:_p,decision:_d,...rest}=game;if(value==='pk_advance')return {...rest,result:'tie',decision:'advanced_on_penalties',completed:true};if(value==='pk_elimination')return {...rest,result:'tie',decision:'eliminated_on_penalties',completed:true};return {...rest,result:value as Outcome,completed:true};})});}
  function remove(team:string){const game=config.fixed_games.find(row=>row.team===team)!;if(game.category==='conference'){onChange({...config,fixed_games:config.fixed_games.map(row=>{if(row.team!==team)return row;const {completed:_c,...rest}=row;return rest;})});}else onChange({...config,fixed_games:config.fixed_games.filter(row=>row.team!==team)});}
  return <details open={expanded||undefined} className="panel conference-panel season-record-panel"><summary><span><CalendarDays size={17}/><strong>Current season results</strong><span className="count-pill">{counts[0]} W · {counts[1]} T · {counts[2]} L</span></span><ChevronDown size={17}/></summary><div className="conference-list"><p>Add each completed game by opponent. This is the only accurate way to build a current record because every opponent has a different NPI.</p>
    <div className="sync-panel"><div className="sync-panel-head"><span><RefreshCw size={14}/>Amherst Athletics</span><Button variant="outline" size="sm" disabled={disabled||syncing} onClick={checkForResults}>{syncing?'Checking…':'Check for new NESCAC results'}</Button></div>
      {sync?.error&&<p className="field-note warning-text">{sync.error}</p>}
      {sync&&!sync.error&&!pending.length&&<p className="field-note">No new completed conference games found.</p>}
      {pending.map(item=><div className="sync-row" key={item.team}><span><strong>{item.team}</strong>{item.date&&<small>{item.date}</small>}</span><span className={`status-pill ${item.result}`}>{item.result}{item.score?` · ${item.score}`:''}</span><Button size="sm" disabled={disabled} onClick={()=>{setOutcome(item.team,item.result);setDismissed(prev=>new Set(prev).add(item.team));}}>Confirm</Button><Button variant="ghost" size="sm" disabled={disabled} onClick={()=>setDismissed(prev=>new Set(prev).add(item.team))}>Dismiss</Button></div>)}
    </div>
    <div className="add-result"><Plus size={16}/><Combobox items={available} value={null} onValueChange={team=>team&&add(String(team))} disabled={disabled}><ComboboxInput aria-label="Add a completed opponent" placeholder="Add a completed opponent…"/><ComboboxContent><ComboboxEmpty>No team found.</ComboboxEmpty><ComboboxList>{(team:string)=><ComboboxItem key={team} value={team}>{team}</ComboboxItem>}</ComboboxList></ComboboxContent></Combobox></div>{completed.map(game=>{const value=game.decision==='advanced_on_penalties'?'pk_advance':game.decision==='eliminated_on_penalties'?'pk_elimination':game.result!;return <div className="conference-row result-row" key={game.team}><div><span>{game.team}</span><small>{game.category==='conference'?'NESCAC':'Nonconference'}</small></div><Choice label={`${game.team} completed result`} value={value} disabled={disabled} options={[{value:'win',label:'Win'},{value:'tie',label:'Tie'},{value:'pk_advance',label:'Tie · advanced on penalties'},{value:'pk_elimination',label:'Tie · eliminated on penalties'},{value:'loss',label:'Loss'}]} onChange={next=>setOutcome(game.team,next)}/><Button variant="ghost" size="icon" disabled={disabled} aria-label={`Remove completed result for ${game.team}`} onClick={()=>remove(game.team)}><X size={15}/></Button></div>;})}{!completed.length&&<div className="empty-state compact-empty">No completed games entered yet.</div>}<div className="record-summary"><span>Current record</span><strong>{counts[0]}-{counts[2]}-{counts[1]}</strong><small>{fmt(counts[0]+counts[1]/2,1)} win-equivalents</small></div></div></details>;
}

export function Conference({config,data,onChange,disabled,expanded=false}: {config:Config;data:Bootstrap;onChange:(c:Config)=>void;disabled:boolean;expanded?:boolean}) {
  const conference=config.fixed_games.filter(game=>game.category==='conference');
  const counts=(['win','tie','loss'] as Outcome[]).map(outcome=>conference.filter(game=>game.result===outcome).length);
  const completedCounts=(['win','tie','loss'] as Outcome[]).map(outcome=>conference.filter(game=>game.completed&&game.result===outcome).length);
  const [finish,setFinish]=useState(counts.map(String));
  useEffect(()=>setFinish(counts.map(String)),[counts.join(':')]);
  const finishNumbers=finish.map(Number),finishValid=finish.every(value=>value!==''&&Number.isInteger(Number(value))&&Number(value)>=0)&&finishNumbers.reduce((sum,value)=>sum+value,0)===conference.length&&finishNumbers.every((value,i)=>value>=completedCounts[i]);
  function applyCounts(target:number[]){const remaining=target.map((value,i)=>value-completedCounts[i]);if(remaining.some(value=>value<0))return;const npi=new Map(data.teams.map(team=>[team.name,team.npi]));const ordered=conference.filter(game=>!game.completed).sort((a,b)=>(npi.get(a.team)??0)-(npi.get(b.team)??0)||a.team.localeCompare(b.team));const results=new Map(ordered.map((game,i)=>[game.team,i<remaining[0]?'win':i<remaining[0]+remaining[1]?'tie':'loss'] as const));onChange({...config,fixed_games:config.fixed_games.map(game=>{if(game.category!=='conference'||game.completed)return game;const {probabilities:_p,decision:_d,...rest}=game;return {...rest,result:results.get(game.team) as Outcome};})});}
  function applyFinish(){if(finishValid)applyCounts(finishNumbers);}
  const presets=FINISH_PRESETS.map(preset=>{
    const target=scaleFinish(preset.ratios,conference.length);
    const valid=target.every((value,i)=>value>=completedCounts[i]);
    const on=conference.length>0&&counts[0]===target[0]&&counts[1]===target[1]&&counts[2]===target[2];
    return {...preset,target,valid,on,rate:conference.length?(target[0]+target[1]/2)/conference.length:0};
  });
  function setOutcome(team:string,value:string){onChange({...config,fixed_games:config.fixed_games.map(game=>{if(game.team!==team)return game;const {result:_r,probabilities:_p,decision:_d,...rest}=game;if(value==='uncertain'){const {completed:_c,...open}=rest;return open;}if(value==='pk_advance')return {...rest,result:'tie',decision:'advanced_on_penalties'};if(value==='pk_elimination')return {...rest,result:'tie',decision:'eliminated_on_penalties'};return {...rest,result:value as Outcome};})});}
  return <details open={expanded||undefined} className="panel conference-panel"><summary><span><LockKeyhole size={17}/><strong>NESCAC finish scenario</strong><span className="count-pill">{counts[0]} W · {counts[1]} T · {counts[2]} L</span></span><ChevronDown size={17}/></summary><div className="conference-list"><div className="finish-cards">{presets.map(preset=><button type="button" key={preset.key} className={`finish-card ${preset.on?'on':''}`} disabled={disabled||!preset.valid} onClick={()=>applyCounts(preset.target)}><span>{preset.eyebrow}</span><strong>{preset.target[0]}-{preset.target[2]}-{preset.target[1]}</strong><em>{fmt(preset.rate,3).replace(/^0/,'')} win rate</em><p>{preset.note}</p><b>{preset.on?<><Check size={14}/>Planning around this</>:'Use this finish'}</b></button>)}</div><div className="finish-builder"><div><strong>Try a different conference finish</strong><p>Enter a record totaling {conference.length} games. Completed results stay locked; open results are assigned by opponent NPI and can be changed below.</p></div><div className="finish-fields">{['Wins','Ties','Losses'].map((label,i)=><label key={label}>{label}<input aria-label={`Scenario ${label.toLowerCase()}`} type="number" min="0" max={conference.length} step="1" disabled={disabled} value={finish[i]} onChange={event=>setFinish(values=>values.map((value,j)=>j===i?event.target.value:value))}/></label>)}<Button variant="outline" disabled={disabled||!finishValid} onClick={applyFinish}>Apply finish</Button></div>{!finishValid&&<p className="form-error">The finish must total {conference.length} games and include every completed result.</p>}</div><p>The ten conference opponents stay fixed. A completed result is marked below; penalty-kick decisions still enter the NPI as ties.</p>{conference.map(game=>{const value=game.decision==='advanced_on_penalties'?'pk_advance':game.decision==='eliminated_on_penalties'?'pk_elimination':game.result||'uncertain';return <div className="conference-row" key={game.team}><span>{game.team}{game.completed&&<small className="played-label">played</small>}</span><Choice label={`${game.team} outcome`} value={value} disabled={disabled} options={[{value:'uncertain',label:'Not played yet'},{value:'win',label:'Win'},{value:'tie',label:'Tie'},{value:'pk_advance',label:'Tie · advanced on penalties'},{value:'pk_elimination',label:'Tie · eliminated on penalties'},{value:'loss',label:'Loss'}]} onChange={v=>setOutcome(game.team,v)}/></div>;})}</div></details>;
}
