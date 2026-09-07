import { compile } from 'tailwindcss';
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { Plugin } from 'vite';

export function pureStyles(): Plugin {
  const root = dirname(fileURLToPath(import.meta.url));
  const walk = (dir: string): string[] => readdirSync(dir, {withFileTypes:true}).flatMap(e =>
    e.isDirectory() ? walk(join(dir,e.name)) : /\.(tsx?|css)$/.test(e.name) ? [join(dir,e.name)] : []);
  return {name:'schedule-lab-styles', enforce:'pre', async load(id) {
    if (id.split('?')[0] !== join(root,'app/globals.css')) return;
    const files = ['app','components','hooks','lib'].flatMap(d=>walk(join(root,d)));
    files.forEach(f=>this.addWatchFile(f));
    const candidates = new Set(files.flatMap(f=>readFileSync(f,'utf8').match(/[^\s"'`]+/g) || []));
    const compiler = await compile(readFileSync(join(root,'app/globals.css'),'utf8'), {
      base:join(root,'app'),
      async loadStylesheet(name, base) {
        const aliases: Record<string,string> = {
          tailwindcss:'tailwindcss/index.css', 'tw-animate-css':'tw-animate-css/dist/tw-animate.css',
        };
        const path = name.startsWith('.') ? resolve(base,name) : join(root,'node_modules',aliases[name] || name);
        return {path,base:dirname(path),content:readFileSync(path,'utf8')};
      },
    });
    return compiler.build([...candidates]);
  }};
}
