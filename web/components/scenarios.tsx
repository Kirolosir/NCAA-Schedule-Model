'use client';
import { useEffect, useRef, useState } from 'react';
import { FolderOpen, Plus, Save, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Config } from '@/lib/model';
import { downloadPlan, readPlanFile } from '@/lib/plan-files';

type SavedScenario = {id:string;name:string;savedAt:string;config:Config};
const STORAGE_KEY='schedule-lab-plans-v1';
const CHANGE_EVENT='schedule-lab-plans-changed';

function readSaved():SavedScenario[] {
  const value=JSON.parse(localStorage.getItem(STORAGE_KEY)||'[]');
  if(!Array.isArray(value)||value.some(row=>!row||typeof row.id!=='string'||typeof row.name!=='string'||typeof row.savedAt!=='string'||!row.config||typeof row.config.season!=='string'||!Array.isArray(row.config.candidates)))throw new Error('Saved plans could not be read. The existing browser data has been preserved.');
  return value;
}

export function useSavedScenarios() {
  const [saved,setSaved]=useState<SavedScenario[]>([]);
  const [storageError,setStorageError]=useState('');
  useEffect(()=>{
    const refresh=()=>{try{setSaved(readSaved());setStorageError('');}catch(error){setStorageError((error as Error).message);}};
    refresh();window.addEventListener(CHANGE_EVENT,refresh);window.addEventListener('storage',refresh);
    return()=>{window.removeEventListener(CHANGE_EVENT,refresh);window.removeEventListener('storage',refresh);};
  },[]);
  function persist(update:(current:SavedScenario[])=>SavedScenario[]){
    try{const next=update(readSaved());localStorage.setItem(STORAGE_KEY,JSON.stringify(next));setSaved(next);setStorageError('');window.dispatchEvent(new Event(CHANGE_EVENT));return true;}
    catch(error){setStorageError((error as Error).message);return false;}
  }
  function save(name:string,config:Config){
    const clean=name.trim();if(!clean||clean.length>80)return false;
    return persist(current=>[{id:crypto.randomUUID(),name:clean,savedAt:new Date().toISOString(),config:structuredClone(config)},...current]);
  }
  function remove(id:string){persist(current=>current.filter(row=>row.id!==id));}
  return {saved,save,remove,storageError};
}

function PlanTransfers({save,config,name}:{save:(name:string,config:Config)=>boolean;config?:Config;name?:string}) {
  const fileInput=useRef<HTMLInputElement>(null);
  const [busy,setBusy]=useState(false),[message,setMessage]=useState('');
  async function importFile(file?:File){
    if(!file)return;setBusy(true);setMessage('Checking the plan file…');
    try{const imported=await readPlanFile(file);if(!save(imported.name,imported.config))throw new Error('The browser could not save the imported plan. Existing plans were preserved.');setMessage(`${imported.name} imported. ${imported.notices.join(' ')}`);}
    catch(error){setMessage((error as Error).message);}finally{setBusy(false);if(fileInput.current)fileInput.current.value='';}
  }
  async function exportFile(){if(!config)return;setBusy(true);setMessage('');try{await downloadPlan(name?.trim()||`${config.target_team} ${config.season} plan`,config);setMessage('Setup exported. Open Saved plans on another computer to import it.');}catch(error){setMessage((error as Error).message);}finally{setBusy(false);}}
  return <div className="plan-transfers"><div><Button variant="outline" disabled={busy} onClick={()=>fileInput.current?.click()}>Import setup file</Button>{config&&<Button variant="outline" disabled={busy} onClick={exportFile}>Export current setup</Button>}<input ref={fileInput} type="file" accept=".json,application/json" aria-label="Import a portable plan file" className="sr-only" onChange={event=>void importFile(event.target.files?.[0])}/></div>{message&&<p role="status" className="field-note">{message}</p>}<p className="field-note">Portable files preserve setup, playoff entries, and data fingerprints. Results are recalculated after import. Import adds a copy and keeps existing plans.</p></div>;
}

function SavedRow({item,onOpen,onRemove}:{item:SavedScenario;onOpen:(config:Config)=>void;onRemove:()=>void}) {
  const [error,setError]=useState(''),[exporting,setExporting]=useState(false);
  return <div className="portable-saved-row"><div><strong>{item.name}</strong><span>{item.config.season} data · {item.config.candidates.length} teams · saved {new Date(item.savedAt).toLocaleDateString()}</span>{error&&<p className="form-error" role="alert">{error}</p>}</div><div className="saved-row-actions"><Button variant="outline" onClick={()=>onOpen(structuredClone(item.config))}>Open</Button><Button variant="outline" disabled={exporting} onClick={async()=>{setExporting(true);setError('');try{await downloadPlan(item.name,item.config);}catch(failure){setError((failure as Error).message);}finally{setExporting(false);}}}>Export</Button><Button variant="ghost" size="icon" aria-label={`Delete ${item.name}`} onClick={onRemove}><Trash2 size={15}/></Button></div></div>;
}

export function Scenarios({config,onOpen,disabled}: {config:Config;onOpen:(config:Config)=>void;disabled:boolean}) {
  const [open,setOpen]=useState(false),[name,setName]=useState(''),[message,setMessage]=useState('');
  const {saved,save,remove,storageError}=useSavedScenarios();
  function handleSave(){if(save(name,config)){setName('');setMessage(`${name.trim()} saved in this browser.`);}else setMessage('Could not save this plan. Check the name and browser storage.');}
  return <><Button variant="outline" disabled={disabled} onClick={()=>setOpen(true)}><FolderOpen size={16}/>Saved plans{saved.length?` (${saved.length})`:''}</Button><Dialog open={open} onOpenChange={setOpen}><DialogContent className="scenario-dialog"><DialogHeader><DialogTitle>Planning scenarios</DialogTitle><DialogDescription>Save here, or export a portable setup to reopen on another computer.</DialogDescription></DialogHeader>
    <div className="scenario-save"><input aria-label="Scenario name" maxLength={80} placeholder="Example: Fall 2027 travel plan" value={name} onChange={e=>setName(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')handleSave();}}/><Button disabled={!name.trim()||!!storageError} onClick={handleSave}><Save size={15}/>Save current plan</Button></div>{message&&<p className="scenario-message" role="status">{message}</p>}{storageError&&<p className="form-error" role="alert">{storageError}</p>}
    <PlanTransfers save={save} config={config} name={name}/>
    <div className="portable-saved-list">{saved.map(item=><SavedRow key={item.id} item={item} onOpen={next=>{onOpen(next);setOpen(false);}} onRemove={()=>remove(item.id)}/>)}{!saved.length&&!storageError&&<div className="empty-state">No saved planning scenarios yet.</div>}</div>
  </DialogContent></Dialog></>;
}

export function SavedPlansScreen({onOpen,onStartNew}: {onOpen:(config:Config)=>void;onStartNew:()=>void}) {
  const {saved,save,remove,storageError}=useSavedScenarios();
  return <main className="saved-screen"><div className="saved-inner"><h1>Saved plans</h1><p>Keep plans in this browser or export a setup file to share and reopen elsewhere.</p><PlanTransfers save={save}/>{storageError&&<p className="form-error" role="alert">{storageError}</p>}
    <div className="portable-saved-list">{saved.map(item=><SavedRow key={item.id} item={item} onOpen={onOpen} onRemove={()=>remove(item.id)}/>)}{!saved.length&&!storageError&&<div className="empty-state">No saved plans yet. Import a setup or start a new plan.</div>}</div>
    <Button className="primary-action" onClick={onStartNew}><Plus size={17}/>Start a new plan</Button>
  </div></main>;
}
