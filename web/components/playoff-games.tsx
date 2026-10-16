import { Plus, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Combobox, ComboboxContent, ComboboxEmpty, ComboboxInput, ComboboxItem, ComboboxList } from '@/components/ui/combobox';
import { Choice } from '@/components/planning-controls';
import { Bootstrap, Config, Outcome, PlayoffGame } from '@/lib/model';

export function PlayoffGames({data,config,onChange,disabled}:{data:Bootstrap;config:Config;onChange:(config:Config)=>void;disabled:boolean}) {
  const games=config.playoff_games??[];
  const teams=data.teams.map(team=>team.name).filter(team=>team!==config.target_team).sort();
  function update(id:string,change:(game:PlayoffGame)=>PlayoffGame){onChange({...config,playoff_games:games.map(game=>game.game_id===id?change(game):game)});}
  function outcome(id:string,value:string){update(id,game=>{
    const {result:_r,decision:_d,probabilities:_p,completed:_c,...rest}=game;
    if(value==='model')return rest;
    const decision=value==='pk_advance'?'advanced_on_penalties':value==='pk_elimination'?'eliminated_on_penalties':undefined;
    return {...rest,result:decision?'tie':value as Outcome,...(decision?{decision}:{}),...(game.completed?{completed:true}:{})};
  });}
  return <section className="panel playoff-panel"><div className="panel-heading"><div><h2>Playoff games</h2><p>Every entry is an additional game, included in every proposed schedule. You can face an earlier opponent again.</p></div><span className="count-pill">{games.length} added</span></div><div className="playoff-body">
    <div className="add-result"><Plus size={16}/><Combobox items={teams} value={null} disabled={disabled} onValueChange={team=>{if(team)onChange({...config,playoff_games:[...games,{game_id:`playoff:${crypto.randomUUID()}`,team:String(team),round:'Quarterfinal'}]});}}><ComboboxInput aria-label="Add a playoff opponent" placeholder="Add a playoff opponent…"/><ComboboxContent><ComboboxEmpty>No team found.</ComboboxEmpty><ComboboxList>{(team:string)=><ComboboxItem key={team} value={team}>{team}</ComboboxItem>}</ComboboxList></ComboboxContent></Combobox></div>
    {games.map(game=>{
      const value=game.decision==='advanced_on_penalties'?'pk_advance':game.decision==='eliminated_on_penalties'?'pk_elimination':game.result??'model';
      return <article className="playoff-game" key={game.game_id}><div className="playoff-game-head"><strong>{game.team}</strong><Button variant="ghost" size="icon" disabled={disabled} aria-label={`Remove ${game.team} ${game.round}`} onClick={()=>onChange({...config,playoff_games:games.filter(row=>row.game_id!==game.game_id)})}><X size={15}/></Button></div><div className="planning-fields"><label className="field">Round<Choice label={`${game.team} playoff round`} value={game.round} disabled={disabled} onChange={round=>update(game.game_id,row=>({...row,round:round as PlayoffGame['round']}))} options={['Quarterfinal','Semifinal','Final','Playoff'].map(round=>({value:round,label:round}))}/></label><label className="field">Outcome<Choice label={`${game.team} ${game.round} outcome`} value={value} disabled={disabled} onChange={next=>outcome(game.game_id,next)} options={[{value:'model',label:'Use historical model'},{value:'win',label:'Assume win'},{value:'tie',label:'Assume draw'},{value:'loss',label:'Assume loss'},{value:'pk_advance',label:'Draw · advanced on penalties'},{value:'pk_elimination',label:'Draw · eliminated on penalties'}]}/></label></div>
        <div className="assume-outcome" role="group" aria-label={`${game.team} ${game.round} assumed result`}>{(['win','tie','loss'] as Outcome[]).map(result=><button type="button" disabled={disabled} key={result} aria-pressed={game.result===result} onClick={()=>outcome(game.game_id,result)}>Assume {result==='tie'?'draw':result}</button>)}</div>
        <label className="playoff-completed"><Checkbox checked={!!game.completed} disabled={disabled||!game.result} aria-label={`${game.team} ${game.round} already played`} onCheckedChange={checked=>update(game.game_id,row=>({...row,completed:!!checked}))}/>Already played · count in current record</label>
      </article>;
    })}
    <p className="field-note">Playoff entries do not use regular-season pool slots. Add only rounds you want this scenario to include; later rounds are not generated automatically. Penalty-kick decisions count as NPI draws.</p>
  </div></section>;
}
