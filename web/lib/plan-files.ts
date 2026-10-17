import { api, Config, ImportedPlan, PortablePlan } from '@/lib/model';

export async function downloadPlan(name:string,config:Config) {
  const file=await api<PortablePlan>('plans/export',{name,config});
  const url=URL.createObjectURL(new Blob([JSON.stringify(file,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;
  link.download=`${name.replace(/[^a-zA-Z0-9_-]+/g,'-').replace(/^-|-$/g,'')||'schedule-lab'}.plan.json`;
  link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

export async function readPlanFile(file:File):Promise<ImportedPlan> {
  if(file.size>100000)throw new Error('Choose a plan file smaller than 100 KB. Full result reports are separate from portable setups.');
  let contents:unknown;
  try{contents=JSON.parse((await file.text()).replace(/^\uFEFF/,''));}
  catch{throw new Error('This file is not valid JSON. Choose a .plan.json file exported by Schedule Lab.');}
  return api<ImportedPlan>('plans/import',contents);
}
