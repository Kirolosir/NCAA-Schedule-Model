'use client';
import { useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, Check, CircleHelp, LoaderCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Conference, Pool, SeasonRecord, Settings } from '@/components/planning-controls';
import { Forecast } from '@/components/results';
import { Bootstrap, Config, Schedule, Validation, fmt } from '@/lib/model';

const STEPS = [
  {title:'What are you aiming for?',short:'Goal',description:'Set the NPI target and enter games already played. Everything else is optional.'},
  {title:'How do you expect NESCAC to go?',short:'Conference',description:'Your ten conference games are already on the calendar. Pick the finish you want to plan around.'},
  {title:'Who could you realistically play?',short:'Opponents',description:'Add every team that would take the game. We will pick the best combination from this list.'},
  {title:'Any limits we should respect?',short:'Review',description:'Set practical limits, then choose how carefully to run the comparison.'},
];

function step(target:number,delta:number){return Math.max(0,Math.min(100,Math.round((target+delta)*10)/10));}

export function Wizard({data,config,validation,validationError,onChange,onReset,onExit,disabled,stale,schedule,onStart,step:current,onStepChange}:{
  data:Bootstrap;config:Config;validation:Validation|null;validationError:string;onChange:(config:Config)=>void;
  onReset:()=>void;onExit:()=>void;disabled:boolean;stale:boolean;schedule:Schedule|undefined;onStart:()=>Promise<unknown>;
  step:number;onStepChange:(step:number)=>void;
}) {
  const [furthest,setFurthest]=useState(current);
  useEffect(()=>setFurthest(value=>Math.max(value,current)),[current]);
  const candidateCount=validation?.candidate_count??config.candidates.filter(candidate=>!config.excluded.includes(candidate.team)).length;
  const canContinue=current!==2||Boolean(validation);
  function move(next:number){onStepChange(Math.max(0,Math.min(STEPS.length-1,next)));window.scrollTo({top:0,behavior:'smooth'});}
  function back(){if(current===0)onExit();else move(current-1);}
  const active=STEPS[current];
  const hints=['Takes about a minute','You can change this later',`${candidateCount} team${candidateCount===1?'':'s'} in the pool · add more for better options`,'Nothing else to enter'];
  return <div className="wizard-screen">
    <header className="step-header"><div className="step-header-inner">
      {STEPS.map((item,index)=>{
        const done=index<current,isActive=index===current,available=index<=furthest+1;
        return <button type="button" key={item.title} className={isActive?'active':done?'done':''} disabled={disabled||!available} onClick={()=>move(index)}>
          <span className="step-mark">{done?<Check size={14}/>:index+1}</span>
          <span className="step-header-label"><small>STEP {index+1}</small><strong>{item.short}</strong></span>
          {index<STEPS.length-1&&<span className="step-divider"/>}
        </button>;
      })}
    </div></header>

    <main className="wizard-main"><div className="wizard-main-inner">
      <h1>{active.title}</h1>
      <p className="step-intro">{active.description}</p>

      {current===0&&<div className="goal-grid">
        <section className="goal-card">
          <strong>Target season NPI</strong>
          <p>The rating you want to finish at. This is the number every proposed schedule will be measured against.</p>
          <div className="npi-stepper">
            <button type="button" disabled={disabled} aria-label="Lower target NPI" onClick={()=>onChange({...config,target_npi:step(config.target_npi,-.5)})}>−</button>
            <input aria-label="Target season NPI" type="number" min="0" max="100" step="0.1" disabled={disabled} value={config.target_npi} onChange={event=>{const value=event.currentTarget.valueAsNumber;if(Number.isFinite(value))onChange({...config,target_npi:value});}}/>
            <button type="button" disabled={disabled} aria-label="Raise target NPI" onClick={()=>onChange({...config,target_npi:step(config.target_npi,.5)})}>+</button>
          </div>
          <div className="goal-note"><CircleHelp size={16}/><p>The model treats this as the line to clear, not a prediction.</p></div>
        </section>
        <SeasonRecord config={config} data={data} onChange={onChange} disabled={disabled} expanded/>
      </div>}

      {current===1&&<Conference config={config} data={data} onChange={onChange} disabled={disabled} expanded/>}

      {current===2&&<>
        <Pool data={data} config={config} validation={validation} onChange={onChange} disabled={disabled}/>
        {validationError&&<div className="notice error" role="alert">{validationError}</div>}
      </>}

      {current===3&&<>
        <div className="wizard-review-grid">
          <Settings config={config} onChange={onChange} onReset={onReset} disabled={disabled}/>
          <Forecast schedule={schedule} stale={stale}/>
        </div>
        <div className="wizard-summary">
          <div><span>Schedule size</span><strong>{config.open_slots} games</strong></div>
          <div><span>Available opponents</span><strong>{candidateCount}</strong></div>
          <div><span>Comparison speed</span><strong>{config.analysis_mode}</strong></div>
          <div><span>Target</span><strong>{fmt(config.target_npi)} NPI</strong></div>
        </div>
        {stale&&<div className="stale-note" role="status"><CircleHelp size={16}/><span>Inputs have changed. The forecast above belongs to your previous comparison.</span></div>}
      </>}
    </div></main>

    <footer className="wizard-footer"><div className="wizard-footer-inner">
      <Button variant="outline" disabled={disabled} onClick={back}><ArrowLeft size={16}/>{current===0?'Back to start':`Back to ${STEPS[current-1].short.toLowerCase()}`}</Button>
      <div style={{display:'flex',alignItems:'center',gap:18}}>
        <span className="wizard-footer-hint">{hints[current]}</span>
        {current<3
          ?<Button className="primary-action" disabled={disabled||!canContinue} onClick={()=>move(current+1)}>Continue<ArrowRight size={16}/></Button>
          :<Button className="primary-action" disabled={disabled||!validation} onClick={()=>void onStart().catch(()=>{})}>{disabled?<><LoaderCircle size={16} className="spin"/>Comparing…</>:<>Compare {validation?.combinations??''} schedules<ArrowRight size={16}/></>}</Button>}
      </div>
    </div></footer>
  </div>;
}
