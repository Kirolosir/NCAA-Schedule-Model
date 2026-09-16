'use client';
import { useEffect, useRef, useState } from 'react';
import { ChartNoAxesCombined, ChevronRight, CircleHelp, FolderOpen, Home as HomeIcon, LoaderCircle, ShieldCheck, SlidersHorizontal, Target, Trophy } from 'lucide-react';
import { Sidebar, SidebarProvider, SidebarContent, SidebarFooter, SidebarHeader, SidebarMenu, SidebarMenuItem, SidebarMenuButton, SidebarTrigger } from '@/components/ui/sidebar';
import { Button } from '@/components/ui/button';
import { Choice, Conference, Settings } from '@/components/planning-controls';
import { Explorer } from '@/components/explorer';
import { Results } from '@/components/results';
import { useSavedScenarios, SavedPlansScreen } from '@/components/scenarios';
import { Wizard } from '@/components/wizard';
import { WelcomeScreen, RunningScreen } from '@/components/screens';
import { api, Bootstrap, Config, fmt, Job, Report, Validation } from '@/lib/model';

type Screen = 'welcome'|'wizard'|'running'|'results'|'explorer'|'saved'|'model';

const FLOW_NAV = [
  {key:'welcome' as const,label:'Start',icon:HomeIcon},
  {key:'wizard' as const,label:'Set up the season',icon:ChartNoAxesCombined},
  {key:'results' as const,label:'Results & report',icon:Trophy},
];
const TOOL_NAV = [
  {key:'explorer' as const,label:'Check one opponent',icon:Target},
  {key:'saved' as const,label:'Saved plans',icon:FolderOpen},
  {key:'model' as const,label:'How the model works',icon:SlidersHorizontal},
];
const SEASON_OPTIONS = [
  {value:'2025',label:'2024–25 · Selection day'},
  {value:'2024',label:'2023–24 · Selection day'},
  {value:'2023',label:'2022–23 · Retrospective'},
  {value:'2022',label:'2021–22 · Retrospective'},
];

export default function Home() {
  const [data,setData]=useState<Bootstrap|null>(null);
  const [season,setSeason]=useState('2025');
  const [config,setConfig]=useState<Config|null>(null);
  const [report,setReport]=useState<Report|null>(null);
  const [screen,setScreen]=useState<Screen>('welcome');
  const [wizardStep,setWizardStep]=useState(0);
  const [error,setError]=useState('');
  const [validation,setValidation]=useState<Validation|null>(null);
  const [validationError,setValidationError]=useState('');
  const [selected,setSelected]=useState(0);
  const [job,setJob]=useState<Job|null>(null);
  const [starting,setStarting]=useState(false);
  const pendingConfig=useRef<Config|null>(null);
  const screenRef=useRef(screen);
  useEffect(()=>{screenRef.current=screen;},[screen]);
  const busy=starting||job?.status==='running'||job?.status==='cancelling';
  const stale=!!report&&JSON.stringify(config)!==JSON.stringify(report.config);
  const schedule=report?.top_schedules[selected];
  const {saved}=useSavedScenarios();

  useEffect(()=>{const abort=new AbortController();api<Bootstrap>(`bootstrap?season=${season}`,undefined,abort.signal).then(d=>{const loaded=pendingConfig.current?.season===season?pendingConfig.current:d.config;pendingConfig.current=null;setData(d);setConfig(loaded);setReport(loaded===d.config?d.report:null);setJob(null);setSelected(0);}).catch(e=>{if(e.name!=='AbortError')setError(e.message);});return()=>abort.abort();},[season]);
  useEffect(()=>{if(!config)return;const abort=new AbortController();setValidation(null);const timer=setTimeout(()=>api<Validation>('validate',config,abort.signal).then(v=>{setValidation(v);setValidationError('');}).catch(e=>{if(e.name!=='AbortError')setValidationError(e.message);}),200);return()=>{clearTimeout(timer);abort.abort();};},[config]);
  useEffect(()=>{
    if(!job?.id||!['running','cancelling'].includes(job.status))return;
    let disposed=false;let timer:ReturnType<typeof setTimeout>;
    const poll=async()=>{try{const next=await api<Job>(`jobs/${job.id}`);if(disposed)return;setJob(next);if(next.status==='complete'&&next.report){setReport(next.report);setSelected(0);setError('');if(screenRef.current==='running')setScreen('results');}else if(next.status==='error'){setError(next.message);if(screenRef.current==='running')setScreen('wizard');}else if(['running','cancelling'].includes(next.status)){timer=setTimeout(poll,600);}}catch(e){if(disposed)return;const message=(e as Error).message;if(message.includes('not found')){setJob(null);setError('The app restarted and this comparison is no longer available. Your current inputs are still here.');if(screenRef.current==='running')setScreen('wizard');}else{setError('The model connection was interrupted. Retrying; your inputs are unchanged.');timer=setTimeout(poll,2000);}}};
    timer=setTimeout(poll,200);return()=>{disposed=true;clearTimeout(timer);};
  },[job?.id,job?.status]);

  async function start(){
    if(!config||busy)throw new Error('A comparison is already running or inputs are not ready.');
    setStarting(true);setError('');setScreen('running');
    try{const result=await api<{id:string}>('jobs',config);setJob({id:result.id,status:'running',message:'Preparing the full division…',progress:0,config});return result;}
    catch(e){setError((e as Error).message);setScreen('wizard');throw e;}
    finally{setStarting(false);}
  }
  function cancel(){if(!job?.id||job.status!=='running')return;const current=job;setJob({...current,status:'cancelled',message:'Comparison cancelled. Your inputs are unchanged.'});setScreen('wizard');void api<Job>(`jobs/${current.id}/cancel`,{}).catch(e=>setError((e as Error).message));}
  function changeSeason(next:string){setData(null);setValidation(null);setReport(null);setError('');setSeason(next);}
  function openScenario(next:Config){setReport(null);setJob(null);setSelected(0);setError('');setValidationError('');setWizardStep(3);if(next.season!==season){pendingConfig.current=next;changeSeason(next.season);}else setConfig(next);setScreen('wizard');}
  function startNew(){setWizardStep(0);setScreen('wizard');}

  return <SidebarProvider style={{'--sidebar-width':'248px'} as React.CSSProperties}>
    <Sidebar className="brand-sidebar"><SidebarHeader className="brand-head"><div className="brand-symbol"><ChartNoAxesCombined size={23}/></div><div><strong>Schedule Lab</strong><span>AMHERST MEN'S SOCCER</span></div></SidebarHeader>
      <SidebarContent>
        <p className="nav-label">BUILD A SCHEDULE</p>
        <SidebarMenu>{FLOW_NAV.map(item=>{
          const isActive=screen===item.key||(item.key==='wizard'&&screen==='running');
          const lockedOut=item.key==='results'&&!report;
          const Icon=item.icon;
          return <SidebarMenuItem key={item.key}><SidebarMenuButton isActive={isActive} disabled={lockedOut} onClick={()=>setScreen(item.key)}><Icon/><span>{item.label}</span>{isActive&&<ChevronRight className="ml-auto"/>}</SidebarMenuButton></SidebarMenuItem>;
        })}</SidebarMenu>
        <div className="nav-divider"/>
        <p className="nav-label">TOOLS</p>
        <SidebarMenu>{TOOL_NAV.map(item=>{const Icon=item.icon;return <SidebarMenuItem key={item.key}><SidebarMenuButton isActive={screen===item.key} onClick={()=>setScreen(item.key)}><Icon/><span>{item.label}</span></SidebarMenuButton></SidebarMenuItem>;})}</SidebarMenu>
      </SidebarContent>
      <SidebarFooter>
        <div className="sidebar-season"><span>HISTORICAL SEASON</span><Choice label="Historical season" value={season} disabled={busy} onChange={changeSeason} options={SEASON_OPTIONS}/></div>
        <div className="verified"><ShieldCheck size={18}/><div><strong>{data?.source.rating_kind==='official_npi'?'Published NPI verified':'Historical reconstruction'}</strong><span>{data?`${data.teams.length} teams · ${data.source.season} data`:'Loading season data'}</span></div></div>
        <div className="local-label"><span/>{data?.deployment?.hosted?'Hosted on Render':'Private, on this computer'}</div>
      </SidebarFooter>
    </Sidebar>

    <div className="workspace">
      <div className="mobile-topbar"><SidebarTrigger className="mobile-trigger"/><strong>Schedule Lab</strong></div>
      {(error||job?.status==='cancelled')&&<div className="top-banner">{error?<div className="notice error" role="alert">{error}{!data&&<Button variant="outline" onClick={()=>window.location.reload()}>Reconnect</Button>}</div>:<div className="notice neutral" role="status">Comparison cancelled. Your previous results and current inputs are unchanged.</div>}</div>}

      {!data||!config?<div className="loading-state" style={{margin:'60px 40px'}}><LoaderCircle className="spin"/><h2>Connecting to the division model</h2><p>The verified historical data will appear here shortly.</p></div>:<>
        {screen==='welcome'&&<WelcomeScreen targetTeam={config.target_team} openSlots={config.open_slots} lastPlan={saved[0]?{name:saved[0].name,savedAt:saved[0].savedAt}:undefined} onStart={startNew} onOpenSaved={()=>setScreen('saved')}/>}

        {(screen==='wizard')&&<Wizard data={data} config={config} validation={validation} validationError={validationError} onChange={setConfig} onReset={()=>{setConfig(data.config);setValidationError('');}} onExit={()=>setScreen('welcome')} disabled={busy} stale={stale} schedule={schedule} onStart={start} step={wizardStep} onStepChange={setWizardStep}/>}

        {screen==='running'&&<RunningScreen teamCount={data.teams.length} message={job?.message??'Preparing the full division…'} progress={job?.progress??0} combinations={validation?.combinations} onCancel={cancel}/>}

        {screen==='results'&&report&&<Results report={report} selected={selected} onSelect={setSelected} stale={stale} onEdit={()=>{setWizardStep(2);setScreen('wizard');}} onOpenScenario={openScenario}/>}

        {screen==='explorer'&&<main className="simple-screen"><div className="simple-inner">
          <Explorer config={config} data={data}/>
          <div className="explorer-bottom"><Conference config={config} data={data} onChange={setConfig} disabled={busy}/><div className="panel teaching-note"><CircleHelp size={22}/><div><h3>Why can a win hurt?</h3><p>Below ten retained win-equivalents, a low-value win still counts and can lower the average. Once the minimum is met, a weak additional win can be excluded. That’s why the same opponent can help one slate and hurt another.</p></div></div></div>
        </div></main>}

        {screen==='saved'&&<SavedPlansScreen onOpen={openScenario} onStartNew={startNew}/>}

        {screen==='model'&&<ModelNotes data={data} config={config} onChange={setConfig} onReset={()=>setConfig(data.config)} disabled={busy}/>}
      </>}
    </div>
  </SidebarProvider>;
}

function ModelNotes({data,config,onChange,onReset,disabled}:{data:Bootstrap;config:Config;onChange:(c:Config)=>void;onReset:()=>void;disabled:boolean}){
  const official=data.source.rating_kind==='official_npi'; const team=data.teams.find(t=>t.name===config.target_team);
  return <main className="model-screen"><div className="model-grid"><div className="main-stack"><section className="panel model-card"><div className="panel-heading"><h2>What happens when you compare</h2><span className="count-pill">Win, tie, or loss</span></div><div className="model-steps">{[['01','Build possible seasons','The starting point is the target NPI and the NESCAC finish you enter. Every open game is tested as a win, tie, or loss.'],['02','Recalculate every Division III team',`Amherst’s schedule changes its opponents’ numbers too, so all ${data.teams.length} team NPIs are recalculated together.`],['03','Show the goal, reward, and risk','Schedules are ranked by average projected NPI and show the goal gap, likely range, all-win and all-loss boundaries, and each opponent’s downside.']].map(([n,title,text])=><div key={n}><span>{n}</span><section><h3>{title}</h3><p>{text}</p></section></div>)}</div></section>
    <section className="panel model-card"><div className="panel-heading"><h2>NPI calculation</h2><ShieldCheck size={20}/></div><div className="model-text"><div className="formula">Game value = 15 win points + 0.85 × opponent NPI</div><p>A win above opponent NPI 54 earns an extra <strong>0.75 × (opponent NPI − 54)</strong>. A tie is evaluated as separate half-win and half-loss components.</p><p>Season aggregation is not a plain average. The team must retain at least ten win-equivalents, with each tie adding half a win. After that floor is reached, the weakest win components may be excluded when they lower the NPI. The lowest-valued result is considered regardless of when the game was played.</p><p>The NCAA publishes the ten-win floor; the exact inclusion order used here was derived from official rating exports and checked against complete division results.</p><p>A penalty-kick decision is still an NPI tie whether Amherst advances or is eliminated. The national championship game is the NCAA exception. A winless team uses 85% of its lowest-rated opponent’s NPI.</p><p>{official?<>The division solver reproduces the published {data.source.season} ratings within <strong>0.001</strong>.</>:<>NPI did not exist in {data.source.season}. These ratings apply the later rules retrospectively to that season’s results.</>} Internal values are not rounded; displayed values are.</p></div></section>
    <section className="panel model-card"><div className="panel-heading"><h2>{config.target_team} by season</h2></div><div className="history-table"><div><strong>Season</strong><strong>Rating</strong><strong>Record</strong><strong>Basis</strong></div>{team?.history.map(row=><div key={row.season}><span>{row.season}</span><strong>{fmt(row.npi??undefined)}</strong><span>{row.record??'Not listed'}</span><span>{row.rating_kind==='official_npi'?'Published NPI':'Retrospective'}</span></div>)}</div></section>
    <section className="panel model-card"><div className="panel-heading"><h2>Historical data and limits</h2></div><div className="model-text"><p><strong>Selection day is the main reference point.</strong> It captures the ratings used for postseason decisions before NCAA tournament games distort the comparison. The app keeps four seasons available: two published NPI seasons and two earlier seasons reconstructed under the same rules.</p><p><strong>This is a planning estimate, not a promise.</strong> The selected season contains {data.source.eligible_npi_games.toLocaleString()} real games through {data.source.cutoff}. Rosters, travel, injuries, and an opponent’s future form are not known.</p>{data.model.method==='prior_season_out_of_time'?<p><strong>Win chances come from earlier results.</strong> The model learns from {data.model.training_seasons.join(' and ')} and checks itself against {data.model.holdout_season}. You can replace its estimate when you know a matchup better.</p>:<p><strong>This view is a historical replay.</strong> It uses that season’s final results, so it is best for learning from the past rather than predicting a future season.</p>}<p><strong>Close schedules should be treated as a tie.</strong> The low-to-high range matters more than a difference of a few hundredths. Only the leading shortlist gets the most thorough check.</p><p><strong>Scheduling availability is not known.</strong> The default opponents are examples until the real candidate list is entered.</p></div></section></div><aside><Settings config={config} onChange={onChange} onReset={onReset} disabled={disabled}/><div className="panel scale-note"><h3>NPI rating is not national rank</h3><p>This season’s NPI ratings run from <strong>{fmt(data.rating_range[0])} to {fmt(data.rating_range[1])}</strong>. A team ranked 75th does not have an NPI of 75.</p><p>Choose “Rank positions” only when you want to compare groups such as top 25, 26–50, or 51–100.</p></div></aside></div></main>;
}
