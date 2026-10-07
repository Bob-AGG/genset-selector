// 前后端一致性回归：对同一批场景，跑真实前端 doSearch 与 Python selection.py，比对结果
const puppeteer = require('puppeteer-core');
const { execFileSync } = require('child_process');
const path = require('path');

const CHROME = '/Users/bob/Library/Caches/ms-playwright/chromium-1234/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing';
const URL = 'http://localhost:8899/index.html';
const ROOT = path.join(__dirname, '..');

// 场景定义（wind 必须等于前端 winding 下拉的 option.value，已用 _probe.js 核对）
const SCENARIOS = [
  // 低压 LSA
  { brand: 'leroysomer', freq: '50Hz', volt: 400, wind: 'Y', pf: 0.8, main: 200, mainUnit: 'kW' },
  { brand: 'leroysomer', freq: '50Hz', volt: 400, wind: 'Y', pf: 0.8, main: 100, mainUnit: 'kVA' },
  { brand: 'leroysomer', freq: '60Hz', volt: 480, wind: 'Y', pf: 0.8, main: 250, mainUnit: 'kW' },
  // 斯坦福
  { brand: '斯坦福', freq: '50Hz', volt: 400, wind: 'Y', pf: 0.8, main: 150, mainUnit: 'kW' },
  // AGG
  { brand: 'AGG KK系列', freq: '50Hz', volt: 400, wind: 'Y', pf: 0.8, main: 300, mainUnit: 'kW' },
  { brand: 'AGG KI系列', freq: '60Hz', volt: 480, wind: 'YY', pf: 0.8, main: 500, mainUnit: 'kW' },
  // 美奥迪
  { brand: '美奥迪 Mecc Alte', freq: '50Hz', volt: 400, wind: 'Y', pf: 0.8, main: 100, mainUnit: 'kW' },
  // 马拉松
  { brand: '马拉松低压', freq: '50Hz', volt: 400, wind: 'Y', pf: 0.8, main: 180, mainUnit: 'kW' },
  // 英格
  { brand: '英格N系列', freq: '50Hz', volt: 400, wind: 'Y', pf: 0.8, main: 50, mainUnit: 'kW' },
  { brand: '英格N3系列', freq: '60Hz', volt: 440, wind: 'Y', pf: 0.8, main: 60, mainUnit: 'kW' },
  // 铨一
  { brand: '铨一QYK', freq: '50Hz', volt: 400, wind: 'Y', pf: 0.8, main: 200, mainUnit: 'kW' },
  { brand: '铨一QYI', freq: '60Hz', volt: 440, wind: 'Y', pf: 0.8, main: 150, mainUnit: 'kW' },
  // 中高压（wind 是 winding_code，模式B）
  { brand: '利莱森玛 LSA 中高压', freq: '50Hz', volt: 3300, wind: '6-3300', pf: 0.8, main: 500, mainUnit: 'kW' },
  { brand: '斯坦福中高压', freq: '50Hz', volt: 6600, wind: '6600V-6900V-W61', pf: 0.8, main: 800, mainUnit: 'kW' },
  // 双功率
  { brand: 'leroysomer', freq: '50Hz', volt: 400, wind: 'Y', pf: 0.8, main: 200, mainUnit: 'kW', standby: 250, standbyUnit: 'kW', st: '27c' },
  // 带海拔温度
  { brand: 'leroysomer', freq: '50Hz', volt: 400, wind: 'Y', pf: 0.8, main: 200, mainUnit: 'kW', alt: 1500, temp: 50 },
];

function pyRun(sc) {
  const script = `
import sys, json, os
sys.path.insert(0, ${JSON.stringify(path.join(ROOT, 'backend'))})
import selection
sc = json.loads(sys.argv[1])
brand = sc['brand']
files = {'leroysomer':'leroysomer.json','利莱森玛 TAL':'leroysomer-tal.json','利莱森玛 LSA 中高压':'leroysomer-hv.json','斯坦福':'stanford.json','斯坦福中高压':'stanford-hv.json','AGG KI系列':'agg-ki.json','AGG KK系列':'agg-kk.json','美奥迪 Mecc Alte':'mecc-alte.json','马拉松低压':'marathon.json','英格N系列':'inger-n.json','英格N3系列':'inger-n3.json','铨一QYK':'qyk.json','铨一QYI':'qyi.json','铨一QYH中高压':'qyh.json','顶一DINGOL':'dingol.json'}
import os
data = json.load(open(os.path.join(${JSON.stringify(ROOT)}, files[brand])))
recs = [r for r in data if r.get('type')=='generator']
r = selection.select(recs, brand, sc['freq'], sc.get('volt'), sc['wind'], sc['pf'],
                     main_power=sc.get('main'), main_unit=sc.get('mainUnit','kW'),
                     standby_power=sc.get('standby'), standby_unit=sc.get('standbyUnit','kW'),
                     standby_temp=sc.get('st','27c'), altitude=sc.get('alt',0), temp=sc.get('temp',40),
                     user_phase=sc.get('phase',3), user_pole=sc.get('pole','4'), opt_code=sc.get('opt','none'))
print(json.dumps({'top': (r['top'] or {}).get('model'), 'total': r['total'], 'passed': r['passed'],
                  'models': [c['model'] for c in r['candidates']]}, ensure_ascii=False))
`;
  const out = execFileSync('python3', ['-c', script, JSON.stringify(sc)], { maxBuffer: 1024 * 1024 * 32 });
  return JSON.parse(out.toString());
}

function hvNameOnly(fe, py) {
  if (fe.length !== py.length) return false;
  for (let i = 0; i < fe.length; i++) {
    const a = fe[i].replace(/\s+\d+V(?:-\d+V)?$/, '').trim();   // 去尾部电压
    const b = py[i];
    if (a !== b && !fe[i].startsWith(b)) return false;
  }
  return true;
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new', protocolTimeout: 180000,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1200 });
  await page.evaluateOnNewDocument(() => {
    window.__alerts = [];
    window.alert = (m) => window.__alerts.push(String(m));
    window.confirm = () => true;
    window.print = () => {};
  });
  await page.goto(URL, { waitUntil: 'networkidle2', timeout: 60000 });
  await new Promise(r => setTimeout(r, 1500));

  let pass = 0, fail = 0;
  for (const sc of SCENARIOS) {
    const py = pyRun(sc);
    // 前端操作
    const fe = await page.evaluate(async (sc) => {
      const sleep = ms => new Promise(r => setTimeout(r, ms));
      // 设品牌
      const gb = document.getElementById('genBrand');
      gb.value = sc.brand; gb.dispatchEvent(new Event('change'));
      await sleep(120);
      // 频率
      document.querySelectorAll('input[name="genFreq"]').forEach(r => { r.checked = (r.value === sc.freq); });
      document.querySelector('input[name="genFreq"]').dispatchEvent(new Event('change'));
      await sleep(60);
      // PF
      if (sc.pf != null) {
        document.querySelectorAll('input[name="genPF"]').forEach(r => { r.checked = (Number(r.value) === sc.pf); });
        const pfEl = document.querySelector('input[name="genPF"]');
        if (pfEl) pfEl.dispatchEvent(new Event('change'));
      }
      // 电压（触发 onVoltChange → 重建接线下拉）
      const gv = document.getElementById('genVolt');
      gv.value = sc.volt; gv.dispatchEvent(new Event('input')); gv.dispatchEvent(new Event('change'));
      await sleep(150);
      // 接线：按 option.value === sc.wind 或文本包含 sc.wind
      const gw = document.getElementById('genWinding');
      let windOk = false;
      for (const o of gw.options) {
        if (o.value === sc.wind || o.text.includes(sc.wind)) { gw.value = o.value; windOk = true; break; }
      }
      gw.dispatchEvent(new Event('change'));
      // 功率
      const pm = document.getElementById('genPowerMain');
      pm.value = sc.main || ''; pm.dispatchEvent(new Event('input'));
      const psd = document.getElementById('genPowerStandby');
      if (psd) { psd.value = sc.standby || ''; psd.dispatchEvent(new Event('input')); }
      // 单位
      if (sc.mainUnit) { const u = document.querySelector('input[name="unitMain"][value="' + sc.mainUnit + '"]'); if (u) { u.checked = true; u.dispatchEvent(new Event('change')); } }
      if (sc.standbyUnit) { const u2 = document.querySelector('input[name="unitStandby"][value="' + sc.standbyUnit + '"]'); if (u2) { u2.checked = true; u2.dispatchEvent(new Event('change')); } }
      if (sc.st === '40c') { const d = document.querySelector('input[name="genDuty"]'); }
      // 海拔温度
      document.getElementById('genAlt').value = sc.alt || 0;
      document.getElementById('genTemp').value = sc.temp == null ? 40 : sc.temp;
      window.__alerts = [];
      try { doSearch(); } catch (e) { window.__alerts.push('ERR:' + e.message); }
      await sleep(120);
      // 提取步骤6 + 候选型号（读 table.full-table：第1列 #、第2列 型号）
      const res = { alerts: window.__alerts.slice(), top: null, models: [], total: null, passed: null, windOk: windOk };
      document.querySelectorAll('.step-header').forEach(h => {
        const t = h.textContent.replace(/\s+/g, ' ');
        if (t.includes('综合判定') && t.includes('无匹配')) res.top = null;
      });
      const ft = document.querySelector('table.full-table');
      if (ft) {
        ft.querySelectorAll('tbody tr').forEach(tr => {
          const tds = tr.querySelectorAll('td');
          if (tds.length >= 2) {
            const isOk = tr.classList.contains('ok');
            const model = tds[1].textContent.replace(/^复制/, '').trim();
            res.models.push(model);
            if (isOk && res.top === null) res.top = model;
          }
        });
        const st = document.querySelector('.stats');
        if (st) {
          const m = st.textContent.match(/共(\d+)款[，,](\d+)款满足/);
          if (m) { res.total = parseInt(m[1]); res.passed = parseInt(m[2]); }
        }
      }
      return res;
    }, sc);

    const modelsMatch = JSON.stringify(fe.models.slice(0, 20)) === JSON.stringify(py.models.map(m => m)) || JSON.stringify(fe.models.slice(0, 20)) === JSON.stringify(py.models.slice(0, 20));
    const topMatch = (fe.top || null) === (py.top || null) || (fe.top || '').startsWith(py.top || '\u0000') || (py.top || '').startsWith(fe.top || '\u0000');
    const ok = (modelsMatch || hvNameOnly(fe.models, py.models)) && topMatch && fe.alerts.length === 0;
    if (ok) pass++; else fail++;
    console.log(`${ok ? '✅' : '❌'} [${sc.brand} ${sc.freq} ${sc.volt}V ${sc.wind} ${sc.main}${sc.mainUnit}] FE=${fe.top}(${fe.models.length}) PY=${py.top}(${py.total}/${py.passed})`);
      if (!ok) {
        console.log(`     fe models: ${fe.models.slice(0, 8).join(',')}`);
        console.log(`     py models: ${py.models.slice(0, 8).join(',')}`);
        if (fe.alerts.length) console.log(`     alerts: ${fe.alerts.join(' | ')}`);
      }
  }
  console.log(`\n=== ${pass} pass / ${fail} fail ===`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})();
