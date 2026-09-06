"""Launch the built local app, reusing its server when already running."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser

ROOT=Path(__file__).resolve().parents[1]
URL='http://127.0.0.1:8765'

def running():
    try:
        with urlopen(URL+'/api/health',timeout=2) as response:
            data=json.load(response)
        if data.get('app')!='ncaa-schedule-lab':
            raise RuntimeError('Port 8765 belongs to another application. Close it before starting Schedule Lab.')
        return True
    except URLError:
        return False

def main():
    parser=argparse.ArgumentParser(description='Open Schedule Lab on this computer')
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    if not (ROOT/'web/dist/client/index.html').exists():
        print('Preparing the dashboard for its first launch…',flush=True)
        subprocess.run(['npm','run','build'],cwd=ROOT/'web',check=True)
    if not running():
        logs=ROOT/'reports'
        logs.mkdir(exist_ok=True)
        with (logs/'app-server.log').open('ab') as log:
            process=subprocess.Popen([sys.executable,'-m','npi_model.app_server'],cwd=ROOT,
                                     stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError('The model could not start. See reports/app-server.log for details.')
            if running(): break
            time.sleep(.2)
        else:
            raise RuntimeError('The model is still starting. Try opening the app again shortly.')
    print(f'Schedule Lab is ready: {URL}',flush=True)
    if not args.no_browser: webbrowser.open(URL)

if __name__=='__main__': main()
