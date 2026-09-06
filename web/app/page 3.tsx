'use client';
import { useEffect, useState } from 'react';
import { ArrowUpRight, ChartNoAxesCombined, ChevronRight, CircleHelp, Layers3, ShieldCheck, SlidersHorizontal, Target } from 'lucide-react';
import { Sidebar, SidebarProvider, SidebarContent, SidebarFooter, SidebarHeader, SidebarMenu, SidebarMenuItem, SidebarMenuButton, SidebarTrigger } from '@/components/ui/sidebar';
import { Button } from '@/components/ui/button';
import { api, Bootstrap, Config, fmt, Report } from '@/lib/model';

const NAV = [{id:'planner',label:'Schedule planner',icon:Layers3},{id:'explorer',label:'Opponent explorer',icon:Target},{id:'assumptions',label:'Model & assumptions',icon:SlidersHorizontal}];
export default function Home() {
  const [data, setData] = useState<Bootstrap | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [view, setView] = useState('planner');
  const [error, setError] = useState('');
  useEffect(() => {api<Bootstrap>('bootstrap').then(d => {setData(d);setConfig(d.config);setReport(d.report);}).catch(e => setError(e.message));}, []);
  const best = report?.top_schedules[0];
  return <SidebarProvider style={{'--sidebar-width': '226px'} as React.CSSProperties}>
    <Sidebar className="brand-sidebar"><SidebarHeader className="brand-head"><div className="brand-symbol"><ChartNoAxesCombined size={23}/></div><div><strong>Schedule Lab</strong><span>COLLEGIATE SOCCER</span></div></SidebarHeader>
      <SidebarContent><div className="program"><div className="monogram">A</div><div><strong>Amherst</strong><span>Men’s soccer · Division III</span></div></div>
        <p className="nav-label">WORKSPACE</p><SidebarMenu>{NAV.map(({id,label,icon:Icon}) => <SidebarMenuItem key={id}><SidebarMenuButton isActive={view===id} onClick={() => setView(id)}><Icon/><span>{label}</span>{view===id&&<ChevronRight className="ml-auto"/>}</SidebarMenuButton></SidebarMenuItem>)}</SidebarMenu>
      </SidebarContent><SidebarFooter><div className="verified"><ShieldCheck size={18}/><div><strong>Verified calculation engine</strong><span>407 teams · NCAA 2024 data</span></div></div><div className="local-label"><span/> Private, on this computer</div></SidebarFooter></Sidebar>
    <div className="workspace"><header className="topbar"><div className="breadcrumb"><SidebarTrigger className="mobile-trigger"/><span>Workspace</span><ChevronRight size={14}/><strong>Schedule planner</strong></div><span className="snapshot"><span/>2024 historical replay</span></header>
      <main className="main-content"><div className="page-heading"><div><p className="eyebrow">AMHERST MEN’S SOCCER</p><h1>Every opponent is a decision.</h1><p>Choose opponents and compare projected season NPI.</p></div><Button className="primary-action" disabled={!config}>Compare schedules <ArrowUpRight size={18}/></Button></div>
        {error&&<div className="notice error" role="alert">{error}</div>}
        <div className="metrics"><div className="metric"><span>FIXED CONFERENCE SLATE</span><div>10 <small>games</small></div><p>Opponents set. Outcomes still open.</p></div><div className="metric"><span>NONCONFERENCE OPPORTUNITIES</span><div>05 <small>open slots</small></div><p>Choose from your candidate pool.</p></div><div className="metric"><span>LEADING PROJECTED NPI</span><div>{fmt(best?.projection.mean)} <ArrowUpRight className="positive" size={22}/></div><p>{best?'Historical reference · 64 validation draws':'Loading the verified reference run…'}</p></div></div>
        <div className="planning-grid"><section className="panel"><div className="panel-heading"><div><h2>Your opponent pool</h2><p>A starting point, ready for your adjustments.</p></div><span className="count-pill">7 candidates</span></div><div className="pool-list">{(config?.candidates || []).map((c,i) => <div className="pool-row" key={c.team}><span className={`team-avatar tint-${i%4}`}>{c.team.split(' ').map(x=>x[0]).slice(0,2).join('')}</span><div className="team-name"><strong>{c.team}</strong><span>Nonconference candidate</span></div><div className="rating"><strong>{fmt(data?.teams.find(t=>t.name===c.team)?.npi)}</strong><span>NPI RATING</span></div><ChevronRight size={16}/></div>)}</div><div className="panel-foot"><ShieldCheck size={16}/>Real historical profiles. Scheduling availability is unconfirmed.</div></section>
        <aside className="panel forecast"><div className="panel-heading"><div><span className="eyebrow">THE CURRENT PICTURE</span><h2>Room to improve.</h2></div><ChartNoAxesCombined size={22}/></div><div className="forecast-number">{fmt(best?.projection.mean)}<span>projected season NPI</span></div><div className="range-visual"><div className="range-line"/><div className="range-dot"/></div><div className="range-labels"><span>{fmt(best?.projection.p10)}<small>10th percentile</small></span><span>{fmt(best?.projection.p90)}<small>90th percentile</small></span></div><div className="insight"><CircleHelp size={18}/><p><strong>Reading the range</strong> The leading schedules are close. Compare the ranges and each opponent’s downside before deciding.</p></div></aside></div>
      </main><footer className="app-footer">NPI Schedule Lab <span>Full precision in the model. Clarity in every decision.</span></footer>
    </div></SidebarProvider>;
}
