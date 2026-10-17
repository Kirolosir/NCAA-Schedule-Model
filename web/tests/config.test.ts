import assert from 'node:assert/strict';
import test from 'node:test';
import { sameConfig, restoreConfig } from '../lib/model.ts';
import type { Config } from '../lib/model.ts';

const plan={season:'2025',target_npi:57,fixed_games:[{team:'Tufts',result:'win'}],
  candidates:[{team:'Babson',probabilities:{win:1,tie:0,loss:0}},{team:'WPI'}],
  playoff_games:[{team:'Tufts',game_id:'playoff:test',round:'Quarterfinal',result:'loss'}]} as Config;

test('portable restore and JSON key order do not make matching results stale',()=>{
  const restored=restoreConfig(plan);
  const serialized=JSON.parse(JSON.stringify(restored));
  const reordered=Object.fromEntries(Object.entries(serialized).reverse()) as Config;
  reordered.candidates[0].probabilities={loss:0,tie:0,win:1};
  assert.equal(sameConfig(restored,reordered),true);
});

test('actual target, probability, and playoff result changes are stale',()=>{
  assert.equal(sameConfig(plan,{...plan,target_npi:58}),false);
  const changed=structuredClone(plan);changed.playoff_games![0].result='win';
  assert.equal(sameConfig(plan,changed),false);
  const probabilities=structuredClone(plan);probabilities.candidates[0].probabilities={win:0,tie:0,loss:1};
  assert.equal(sameConfig(plan,probabilities),false);
  assert.equal(sameConfig(plan,null),false);
});

test('array changes remain meaningful while absent optional fields are equivalent',()=>{
  assert.equal(sameConfig(plan,{...plan,candidates:[...plan.candidates].reverse()}),false);
  assert.equal(sameConfig(plan,{...plan,target_recent_npi:undefined}),true);
});
