'use client';
import { useEffect, useState } from 'react';
import { FolderOpen, Save, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Config } from '@/lib/model';

type SavedScenario = {id:string; name:string; savedAt:string; config:Config};
const STORAGE_KEY='schedule-lab-plans-v1';

export function Scenarios({config,onOpen,disabled}: {config:Config;onOpen:(config:Config)=>void;disabled:boolean}) {
  const [open,setOpen]=useState(false);
  const [name,setName]=useState('');
  const [saved,setSaved]=useState<SavedScenario[]>([]);
  const [message,setMessage]=useState('');
  useEffect(()=>{try{const value=JSON.parse(localStorage.getItem(STORAGE_KEY)||'[]');if(Array.isArray(value))setSaved(value);}catch{}},[]);
  function persist(next:SavedScenario[]){try{localStorage.setItem(STORAGE_KEY,JSON.stringify(next));setSaved(next);return true;}catch{setMessage('This browser could not save the plan. Check its storage settings.');return false;}}
  function save(){
    const clean=name.trim();
    if(!clean)return;
    const next=[{id:crypto.randomUUID(),name:clean,savedAt:new Date().toISOString(),config:structuredClone(config)},...saved];
    if(persist(next)){setName('');setMessage(`${clean} saved in this browser.`);}
  }
  return <><Button variant="outline" disabled={disabled} onClick={()=>setOpen(true)}><FolderOpen size={16}/>Saved plans{saved.length?` (${saved.length})`:''}</Button><Dialog open={open} onOpenChange={setOpen}><DialogContent className="scenario-dialog"><DialogHeader><DialogTitle>Planning scenarios</DialogTitle><DialogDescription>Save this setup and reopen it later on this browser. Results can be recalculated after opening.</DialogDescription></DialogHeader>
    <div className="scenario-save"><input aria-label="Scenario name" placeholder="Example: Fall 2027 travel plan" value={name} onChange={e=>setName(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')save();}}/><Button disabled={!name.trim()} onClick={save}><Save size={15}/>Save current plan</Button></div>{message&&<p className="scenario-message" role="status">{message}</p>}
    <div className="scenario-list">{saved.map(item=><div key={item.id}><div><strong>{item.name}</strong><span>{item.config.season} data · {item.config.candidates.length} teams · saved {new Date(item.savedAt).toLocaleDateString()}</span></div><Button variant="outline" onClick={()=>{onOpen(structuredClone(item.config));setOpen(false);}}>Open</Button><Button variant="ghost" size="icon" aria-label={`Delete ${item.name}`} onClick={()=>persist(saved.filter(row=>row.id!==item.id))}><Trash2 size={15}/></Button></div>)}{!saved.length&&<div className="empty-state">No saved planning scenarios yet.</div>}</div>
  </DialogContent></Dialog></>;
}
