'use client';
import { ArrowRight, FolderOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';

const WELCOME_STEPS = [
  {n:'1',title:'Answer four questions',text:'Your goal, how you expect NESCAC to go, who you could play, and any travel limits.'},
  {n:'2',title:'We do the math',text:'Every combination is played out and every Division III rating is recalculated together.'},
  {n:'3',title:'Get a recommendation',text:'A schedule to sign, the close alternatives, and a report you can share.'},
];

function timeAgo(iso:string){
  const diffMs=Date.now()-new Date(iso).getTime();
  const day=86400000;
  if(diffMs<day)return 'today';
  const days=Math.round(diffMs/day);
  if(days===1)return '1 day ago';
  if(days<30)return `${days} days ago`;
  const months=Math.round(days/30);
  return months===1?'1 month ago':`${months} months ago`;
}

export function WelcomeScreen({targetTeam,openSlots,lastPlan,onStart,onOpenSaved}: {
  targetTeam:string;openSlots:number;lastPlan?:{name:string;savedAt:string};onStart:()=>void;onOpenSaved:()=>void;
}) {
  return <main className="welcome-screen"><div className="welcome-hero">
    <p className="eyebrow">SCHEDULE LAB</p>
    <h1>Pick the {openSlots}-game schedule that gives {targetTeam} the best season.</h1>
    <p>Your ten NESCAC games are fixed. Tell us who you could realistically play, and we will rank every {openSlots}-game combination by the season NPI it is likely to produce.</p>
    <div className="welcome-steps">{WELCOME_STEPS.map(step=><div className="welcome-step" key={step.n}><span>{step.n}</span><strong>{step.title}</strong><p>{step.text}</p></div>)}</div>
    <div className="welcome-actions">
      <Button className="primary-action" onClick={onStart}>Start a new schedule<ArrowRight size={19}/></Button>
      <Button variant="outline" onClick={onOpenSaved}><FolderOpen size={17}/>Open a saved plan</Button>
      {lastPlan&&<span className="last-plan">Last saved: {lastPlan.name} · {timeAgo(lastPlan.savedAt)}</span>}
    </div>
  </div></main>;
}

export function RunningScreen({teamCount,message,progress,combinations,onCancel}: {teamCount:number;message:string;progress:number;combinations?:number;onCancel:()=>void}) {
  const pct=Math.max(0,Math.min(100,Math.round(progress*100)));
  return <main className="running-screen"><div className="running-card">
    <div className="running-spinner"/>
    <h1>Recalculating all {teamCount} teams</h1>
    <p>{message}</p>
    <div className="running-track"><span style={{width:`${pct}%`}}/></div>
    <div className="running-meta"><span>{pct}% complete</span>{combinations!==undefined&&<span>{combinations.toLocaleString()} combinations</span>}</div>
    <Button variant="outline" onClick={onCancel}>Cancel and go back</Button>
  </div></main>;
}
