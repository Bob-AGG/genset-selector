#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从中间结果生成最终 stanford-hv.json(第二版,细分电压独立code,保证code唯一)"""
import json, re

d=json.load(open('/tmp/stanford_hv_records.json'))

VOLT_LABEL={
 '3300V':'3.3kV','4160V':'4.16kV','5500V':'5.5kV','6000V':'6kV',
 '6300V':'6.3kV','6600V':'6.6kV','6900V':'6.9kV','6600V-6900V':'6.6-6.9kV',
 '7200V':'7.2kV','10000V':'10kV','10500V':'10.5kV','11000V':'11kV',
 '10500V-11000V':'10.5-11kV','11400V':'11.4kV','12470V':'12.47kV',
 '13200V':'13.2kV','13800V':'13.8kV',
}

def volt_num(volt_or_code):
    """取排序用电压数值(首个数字)"""
    m=re.search(r'(\d+)',volt_or_code)
    return int(m.group(1)) if m else 0

out=[]
def make_code(volt, note, wind):
    """winding_code: 复合档#/&细分用具体电压+标记,保证唯一"""
    note=note or ''
    if '#' in note and ('6600' in volt):
        return f"6600V(#)-W{wind}"   # 6600V 细分
    if '&' in note and ('6600' in volt):
        return f"6900V(&)-W{wind}"   # 6900V 细分
    if '#' in note and ('10500' in volt):
        return f"10500V(#)-W{wind}"
    if '&' in note and ('10500' in volt):
        return f"11000V(&)-W{wind}"
    return f"{volt}-W{wind}"

def make_label(volt, note, wind):
    note=note or ''
    if '#' in note and '6600' in volt:
        return f"3ph 6.6kV(6600V档) 绕组{wind}"
    if '&' in note and '6600' in volt:
        return f"3ph 6.9kV(6900V档) 绕组{wind}"
    if '#' in note and '10500' in volt:
        return f"3ph 10.5kV(10500V档) 绕组{wind}"
    if '&' in note and '10500' in volt:
        return f"3ph 11kV(11000V档) 绕组{wind}"
    base=VOLT_LABEL.get(volt, volt)
    return f"3ph {base} 绕组{wind}"

for r in d:
    volt=r['wind_volt']; note=r.get('note') or ''; wind=r['winding_id']
    rec={
      'type':'generator',
      'brand':'stanford-hv',
      'model':r['model'],
      'frequency':r['frequency'],
      'winding_code': make_code(volt,note,wind),
      'winding_label': make_label(volt,note,wind),
      'temp_grade':'F',
      'wires':6,
      'pf':0.8,
      'poles':4,
      'exc_std':'',
      'exc_opt':'',
    }
    rec['footnote']= note or None
    rec['winding_id']=wind
    rec['pitch']=r['pitch']
    # 电压排序键(供前端)
    rec['_vollabel']=r.get('wind_volt', volt)
    for key in ['stdby_27c','stdby_40c','cont_h','cont_f','cont_b']:
        kv=r.get(key+'_kVA'); kw=r.get(key+'_kW')
        if kv is not None and kw is not None:
            rec[key+'_kVA']=kv; rec[key+'_kW']=kw
    out.append(rec)

# 排序: 频率 -> 电压数值 -> code -> 型号
out.sort(key=lambda r:(r['frequency'], volt_num(r['winding_code']), r['winding_code'], r['model']))

# code 唯一性校验
codes=[r['winding_code'] for r in out]
dups={c for c in codes if codes.count(c)>1}
if dups:
    print('!! 重复winding_code:',dups)
else:
    print('✓ winding_code 全部唯一')

with open('stanford-hv.json','w',encoding='utf-8') as f:
    json.dump(out,f,ensure_ascii=False,indent=1)
print('已生成 stanford-hv.json, 条数=',len(out))

# 电压档分布(按code汇总,显示排序)
print('\n=== winding_code 档位(按电压数值升序) ===')
from collections import OrderedDict
seen=OrderedDict()
for r in out:
    seen.setdefault(r['winding_code'],0)
    seen[r['winding_code']]+=1
for c,n in seen.items():
    print(f'  {c}: {n}条')
