'use client';
import { useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, Check, CircleHelp, Gauge, Goal, LoaderCircle, ShieldCheck, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Conference, Pool, SeasonRecord, Settings } from '@/components/planning-controls';
import { Forecast } from '@/components/results';
import { Bootstrap, Config, Schedule, Validation, fmt } from '@/lib/model';

const STEPS = [
  {title:'Goal & results',short:'Goal',description:'Set the NPI target and enter games already played.',icon:Goal},
  {title:'NESCAC finish',short:'Conference',description:'Choose the conference result Amherst should plan around.',icon:ShieldCheck},
  {title:'Opponent pool',short:'Opponents',description:'Add realistic teams and their matchup details.',icon:Users},
  {title:'Limits & review',short:'Review',description:'Set practical limits and run the comparison.',icon:Gauge},
];

export function Wizard({data,config,validation,validationError,onChange,onReset,disabled,stale,schedule,onStart}:{
  data:Bootstrap;config:Config;validation:Validation|null;validationError:string;onChange:(config:Config)=>void;
  onReset:()=>void;disabled:boolean;stale:boolean;schedule:Schedule|undefined;onStart:()=>Promise<unknown>;
}) {
  const [step,setStep]=useState(0);
  const [furthest,setFurthest]=useState(0);
  useEffect(()=>setFurthest(value=>Math.max(value,step)),[step]);
  const candidateCount=validation?.candidate_count??config.candidates.filter(candidate=>!config.excluded.includes(candidate.team)).length;
  const canContinue=step!==2||Boolean(validation);
  function move(next:number){setStep(Math.max(0,Math.min(STEPS.length-1,next)));window.requestAnimationFrame(()=>document.querySelector('.wizard-shell')?.scrollIntoView({behavior:'smooth',block:'start'}));}
  const active=STEPS[step];
  return <section className="wizard-shell" aria-label="Schedule planning steps">
    <nav className="wizard-rail" aria-label="Planner progress">{STEPS.map((item,index)=>{const Icon=item.icon,complete=index<step,available=index<=furthest+1;return <button type="button" key={item.title} className={`${index===step?'active ':''}${complete?'complete':''}`} aria-current={index===step?'step':undefined} disabled={disabled||!available} onClick={()=>move(index)}><span>{complete?<Check size={16}/>:<Icon size={17}/>}</span><div><small>STEP {index+1}</small><strong>{item.short}</strong></div></button>;})}</nav>
    <div className="wizard-heading"><div><span>STEP {step+1} OF {STEPS.length}</span><h2>{active.title}</h2><p>{active.description}</p></div>{step===2&&<div className="wizard-count"><strong>{candidateCount}</strong><span>eligible teams</span></div>}</div>
    <div className="wizard-body">
      {step===0&&<><div className="wizard-goal"><div><span>Target season NPI</span><strong>{fmt(config.target_npi)}</strong><p>This is the number every proposed schedule will be measured against.</p></div><label htmlFor="wizard-target-npi">Coach’s target<input id="wizard-target-npi" type="number" min="0" max="100" step="0.1" disabled={disabled} value={config.target_npi} onChange={event=>{const value=event.currentTarget.valueAsNumber;if(Number.isFinite(value))onChange({...config,target_npi:value});}}/></label></div><SeasonRecord config={config} data={data} onChange={onChange} disabled={disabled} expanded/></>}
      {step===1&&<Conference config={config} data={data} onChange={onChange} disabled={disabled} expanded/>}
      {step===2&&<><Pool data={data} config={config} validation={validation} onChange={onChange} disabled={disabled}/>{validationError&&<div className="notice error" role="alert">{validationError}</div>}</>}
      {step===3&&<><div className="wizard-review-grid"><Settings config={config} onChange={onChange} onReset={onReset} disabled={disabled}/><Forecast schedule={schedule} stale={stale}/></div><div className="wizard-summary"><div><span>Schedule size</span><strong>{config.open_slots} games</strong></div><div><span>Available opponents</span><strong>{candidateCount}</strong></div><div><span>Comparison speed</span><strong>{config.analysis_mode}</strong></div><div><span>Target</span><strong>{fmt(config.target_npi)} NPI</strong></div></div>{stale&&<div className="stale-note" role="status"><CircleHelp size={16}/><span>Inputs have changed. The displayed forecast belongs to your previous comparison.</span></div>}</>}
    </div>
    <footer className="wizard-actions"><div><strong>{active.short}</strong><span>{step<3?'Your entries are saved as you continue.':'Review the setup before comparing.'}</span></div><div>{step>0&&<Button variant="outline" disabled={disabled} onClick={()=>move(step-1)}><ArrowLeft size={16}/>Back</Button>}{step<3?<Button className="primary-action" disabled={disabled||!canContinue} onClick={()=>move(step+1)}>Continue<ArrowRight size={16}/></Button>:<Button className="primary-action" disabled={disabled||!validation} onClick={()=>void onStart().catch(()=>{})}>{disabled?<><LoaderCircle size={16} className="spin"/>Comparing…</>:<>Compare {validation?.combinations??''} schedules<ArrowRight size={16}/></>}</Button>}</div></footer>
  </section>;
}
