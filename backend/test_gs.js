const puppeteer = require('puppeteer-core');
const { execFileSync } = require('child_process');
const path = require('path');
const CHROME = '/Users/bob/Library/Caches/ms-playwright/chromium-1234/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing';
const URL = 'http://localhost:8899/index.html';
const ROOT = '/Users/bob/.openclaw/workspace/genset-selector';

const SCENARIOS = [
  { volt: 10000, main: 300, mainUnit: 'kW' },
  { volt: 10500, main: 300, mainUnit: 'kW' },
  { volt: 11000, main: 400, mainUnit: 'kW' },
  { volt: 6000,  main: 300, mainUnit: 'kW' },
  { volt: 6300,  main: 500, mainUnit: 'kW' },
  { volt: 6600,  main: 600, mainUnit: 'kW' },
  { volt: 10000, main: 375, mainUnit: 'kVA' },
  { volt: 6600,  main: 400, mainUnit: 'kW', standby: 450, standbyUnit: 'kW' },
];

function pyRun(sc, wind) {
  const script = `
import sys, json, os
sys.path.insert(0, ${JSON.stringify(path.join(ROOT,'backend'))})
import selection
sc = json.loads(sys.argv[1])
data = json.load(open(os.path.join(${JSON.stringify(ROOT)}, 'inger-gs-hv.json')))
recs = [r for r in data if r.get('type')=='generator']
r = selection.select(recs, '英格GS高压', '50Hz', sc['volt'], sc['wind'], 0.8,
                     main_power=sc.get('main'), main_unit=sc.get('mainUnit','kW'),
                     standby_power=sc.get('standby'), standby_unit=sc.get('standbyUnit','kW'),
                     standby_temp='40c', altitude=0, temp=40,
                     user_phase=3, user_pole='4', opt_code='none')
print(json.dumps({'top': (r['top'] or {}).get('model'), 'total': r['total'], 'passed': r['passed'],
                  'models': [c['model'] for c in r['candidates']]}, ensure_ascii=False))
`;
  const out = execFileSync('python3', ['-c', script, JSON.stringify({...sc, wind})], { maxBuffer: 1024*1024*32 });
  return JSON.parse(out.toString());
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new', protocolTimeout: 180000,
    args: ['--no-sandbox','--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1200 });
  await page.evaluateOnNewDocument(() => {
    window.__alerts = []; window.alert = m => window.__alerts.push(String(m));
    window.confirm = () => true; window.print = () => {};
  });
  await page.goto(URL, { waitUntil: 'networkidle2', timeout: 60000 });
  await new Promise(r => setTimeout(r, 2000));

  let pass=0, fail=0;
  for (const sc of SCENARIOS) {
    const fe = await page.evaluate(async (sc) => {
      const sleep = ms => new Promise(r=>setTimeout(r,ms));
      const gb = document.getElementById('genBrand');
      gb.value = '英格GS高压'; gb.dispatchEvent(new Event('change'));
      await sleep(200);
      document.querySelectorAll('input[name="genFreq"]').forEach(r=>{r.checked=(r.value==='50Hz');});
      document.querySelector('input[name="genFreq"]').dispatchEvent(new Event('change'));
      await sleep(100);
      const gv = document.getElementById('genVolt');
      gv.value = String(sc.volt); gv.dispatchEvent(new Event('input')); gv.dispatchEvent(new Event('change'));
      await sleep(250);
      const gw = document.getElementById('genWinding');
      // 中高压模式：下拉首项是占位「请选择电压档」(value="")，必须跳过
      const wopts = [...gw.options].map(o=>o.value).filter(v=>v!=='');
      if (wopts.length) { gw.value = wopts[0]; gw.dispatchEvent(new Event('change')); }
      await sleep(100);
      const pm = document.getElementById('genPowerMain');
      pm.value = sc.main||''; pm.dispatchEvent(new Event('input'));
      const u = document.querySelector('input[name="unitMain"][value="'+(sc.mainUnit||'kW')+'"]');
      if(u){u.checked=true; u.dispatchEvent(new Event('change'));}
      const psd = document.getElementById('genPowerStandby');
      if(psd && sc.standby){ psd.value = sc.standby; psd.dispatchEvent(new Event('input')); }
      if(sc.standbyUnit){const u2=document.querySelector('input[name="unitStandby"][value="'+sc.standbyUnit+'"]'); if(u2){u2.checked=true;u2.dispatchEvent(new Event('change'));}}
      document.getElementById('genAlt').value = 0;
      document.getElementById('genTemp').value = 40;
      window.__alerts = [];
      try { doSearch(); } catch(e){ window.__alerts.push('ERR:'+e.message); }
      await sleep(200);
      // 型号列里有「复制」按钮，textContent 会带出按钮文字 → 要剔除按钮再取
      const models=[];
      document.querySelectorAll('table.full-table tbody tr').forEach(tr=>{
        const tds=tr.querySelectorAll('td');
        if(tds.length>1){
          const cell=tds[1].cloneNode(true);
          cell.querySelectorAll('button').forEach(b=>b.remove());
          const m=cell.textContent.trim().replace(/\s+\d+V$/,'').trim();   // 去尾部电压后缀
          if(m && !models.includes(m)) models.push(m);
        }
      });
      return { alerts: window.__alerts.slice(), wind: gw.value, windOpts: wopts, models: models.slice(0,10) };
    }, sc);

    if (!fe.wind) { console.log(`❌ [${sc.volt}V ${sc.main}${sc.mainUnit}] 前端无接线选项 / alerts=${JSON.stringify(fe.alerts)}`); fail++; continue; }
    const py = pyRun(sc, fe.wind);
    const feTop = fe.models[0] || null;
    const pyTop = py.top;
    const ok = feTop === pyTop && (fe.models[0]||'').toString() === (py.models[0]||'').toString();
    if (ok) pass++; else fail++;
    console.log(`${ok?'✅':'❌'} [${sc.volt}V ${sc.main}${sc.mainUnit}] wind=${fe.wind} FE=${feTop}(${fe.models.length}) PY=${pyTop}(${py.total}) ${ok?'':'FElist='+JSON.stringify(fe.models)+' PYlist='+JSON.stringify(py.models.slice(0,10))}`);
  }
  console.log(`\n=== 英格GS: ${pass} pass / ${fail} fail ===`);
  await browser.close();
})();
