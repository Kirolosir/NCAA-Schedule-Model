'use client';
import { useEffect, useState } from 'react';
import { FolderOpen, Plus, Save, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Config } from '@/lib/model';

type SavedScenario = {id:string; name:string; savedAt:string; config:Config};
const STORAGE_KEY='schedule-lab-plans-v1';

export function useSavedScenarios() {
  const [saved,setSaved]=useState<SavedScenario[]>([]);
  useEffect(()=>{try{const value=JSON.parse(localStorage.getItem(STORAGE_KEY)||'[]');if(Array.isArray(value))setSaved(value);}catch{}},[]);
  function persist(next:SavedScenario[]){try{localStorage.setItem(STORAGE_KEY,JSON.stringify(next));setSaved(next);return true;}catch{return false;}}
  function save(name:string,config:Config){
    const clean=name.trim();
    if(!clean)return false;
    return persist([{id:crypto.randomUUID(),name:clean,savedAt:new Date().toISOString(),config:structuredClone(config)},...saved]);
  }
  function remove(id:string){persist(saved.filter(row=>row.id!==id));}
  return {saved,save,remove};
}

export function Scenarios({config,onOpen,disabled}: {config:Config;onOpen:(config:Config)=>void;disabled:boolean}) {
  const [open,setOpen]=useState(false);
  const [name,setName]=useState('');
  const [message,setMessage]=useState('');
  const {saved,save,remove}=useSavedScenarios();
  function handleSave(){if(save(name,config)){setName('');setMessage(`${name.trim()} saved in this browser.`);}else setMessage('This browser could not save the plan. Check its storage settings.');}
  return <><Button variant="outline" disabled={disabled} onClick={()=>setOpen(true)}><FolderOpen size={16}/>Saved plans{saved.length?` (${saved.length})`:''}</Button><Dialog open={open} onOpenChange={setOpen}><DialogContent className="scenario-dialog"><DialogHeader><DialogTitle>Planning scenarios</DialogTitle><DialogDescription>Save this setup and reopen it later on this browser. Results can be recalculated after opening.</DialogDescription></DialogHeader>
    <div className="scenario-save"><input aria-label="Scenario name" placeholder="Example: Fall 2027 travel plan" value={name} onChange={e=>setName(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')handleSave();}}/><Button disabled={!name.trim()} onClick={handleSave}><Save size={15}/>Save current plan</Button></div>{message&&<p className="scenario-message" role="status">{message}</p>}
    <div className="scenario-list">{saved.map(item=><div key={item.id}><div><strong>{item.name}</strong><span>{item.config.season} data · {item.config.candidates.length} teams · saved {new Date(item.savedAt).toLocaleDateString()}</span></div><Button variant="outline" onClick={()=>{onOpen(structuredClone(item.config));setOpen(false);}}>Open</Button><Button variant="ghost" size="icon" aria-label={`Delete ${item.name}`} onClick={()=>remove(item.id)}><Trash2 size={15}/></Button></div>)}{!saved.length&&<div className="empty-state">No saved planning scenarios yet.</div>}</div>
  </DialogContent></Dialog></>;
}

export function SavedPlansScreen({onOpen,onStartNew}: {onOpen:(config:Config)=>void;onStartNew:()=>void}) {
  const {saved,remove}=useSavedScenarios();
  return <main className="saved-screen"><div className="saved-inner">
    <h1>Saved plans</h1>
    <p>Plans are kept in this browser on this computer. Print or download anything you need to share from the results page.</p>
    <div className="saved-list">
      {saved.map(item=><div className="saved-row" key={item.id}>
        <div><strong>{item.name}</strong><span>{item.config.season} data · {item.config.candidates.length} teams · saved {new Date(item.savedAt).toLocaleDateString()}</span></div>
        <Button variant="outline" onClick={()=>onOpen(structuredClone(item.config))}>Open</Button>
        <Button variant="ghost" size="icon" aria-label={`Delete ${item.name}`} onClick={()=>remove(item.id)}><Trash2 size={15}/></Button>
      </div>)}
      {!saved.length&&<div className="empty-state">No saved plans yet. Set one up and save it from the results page.</div>}
    </div>
    <Button className="primary-action" onClick={onStartNew}><Plus size={17}/>Start a new plan</Button>
  </div></main>;
}
