#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AGG KI 手册解析器 v7 —— 最终版
pdftotext 主干 + 修正 WIND_RE + 统一 kW/kVA 两列结构
唯一异常: 8.7 KI 444D 的 '30 9' 需合并为 309(kVA)
表结构: 每表 = 组数 × 3 rating × 2 列(kW,kVA)
"""
import re, json

TXT="/tmp/agg_ki.txt"
lines=open(TXT,encoding='utf-8',errors='ignore').read().split('\n')
pages=[]; cur=[]
for l in lines:
    if '\x0c' in l:
        if cur: pages.append(cur); cur=[]
        cur=[l.replace('\x0c','')]
    else: cur.append(l)
if cur: pages.append(cur)

TABLE_PAGES={
 '8.1':[8,9],'8.2':[10,11],'8.3':[12],'8.4':[13],
 '8.5':[14],'8.6':[15],'8.7':[16,17],'8.8':[18,19],'8.9':[20,21],'8.10':[22,23],
 '9.1':[25,26],'9.2':[27,28],'9.3':[29],'9.4':[30],'9.5':[31,32],
 '9.6':[33],'9.7':[34],'9.8':[35],'9.9':[36,37],'9.10':[38,39],
}
VGROUPS={
 '8.1':['190V/220V/380V','200V/230V/400V','208V/240V/415V'],'8.2':['440V/220V'],
 '8.3':['190V/220V/380V','200V/230V/400V','208V/240V/415V'],'8.4':['440V/220V'],
 '8.5':['220-240V'],'8.6':['230V/115V'],
 '8.7':['208V/240V/415V','220V/254V/440V'],'8.8':['500V','520V'],
 '8.9':['550V','600V'],'8.10':['660V','690V'],
 '9.1':['380-400V','208V/416V'],'9.2':['220-230/440-460V','240V/480V'],
 '9.3':['380-400V','208V/416V'],'9.4':['220-230/440-460V','240V/480V'],
 '9.5':['220-240V/380-416V'],'9.6':['220-240V'],
 '9.7':['240V/120V'],'9.8':['220V/240V'],'9.9':['347V/600V'],
 '9.10':['660V/500V','690V/520V'],
}
RATING_KEYS=['cont_40c','stdby_40c','stdby_27c']
WIND_RE=re.compile(r'^(B\d+|D\d+|T\d+(?:/T?\d+)?)$')
NUM=re.compile(r'\d+(?:\.\d+)?')
SKIP=re.compile(r'号绕组|上述参数|解释权|详细参数|励磁系统|出线数|^\s*型号|^\s*kW|^\s*kVA|持续|备用|st\.by|220V/440V')

def row_nums(toks):
    """从剥掉 绕组/pmg/出线 后的 token 里取数字"""
    j=0
    if toks and WIND_RE.fullmatch(toks[0]): j+=1
    if j<len(toks) and toks[j] in ('可选','标配'): j+=1
    if j<len(toks) and toks[j] in ('12','6','4','12/6','6/12'): j+=1
    return toks[j:]

def fix_444d(sec, model, nums_str):
    """8.7 KI 444D: '30 9' -> '309'"""
    return nums_str

def parse():
    records=[]; issues=[]
    for sec,pgs in TABLE_PAGES.items():
        groups=VGROUPS[sec]; ng=len(groups)
        want=ng*3*2   # 每 rating kW,kVA 两列
        for pg in pgs:
            for l in pages[pg]:
                if SKIP.search(l): continue
                mm=re.search(r'\bKI\s?(\d{3}[A-Z]+)\b', l)
                if not mm or not re.match(r'^\d{3}[A-Z]+$', mm.group(1)): continue
                model='KI '+mm.group(1)
                raw=row_nums(l[mm.end():].split())
                nums=[t for t in raw if NUM.fullmatch(t)]
                # 特判 8.7 KI 444D: 合并 30 9 -> 309 (fitz确认同一格)
                if sec=='8.7' and model=='KI 444D' and len(nums)==13:
                    # 序列 ...248 30 9 230... -> 248 309 230...
                    for i in range(len(nums)-1):
                        if nums[i]=='30' and nums[i+1]=='9':
                            nums[i]='309'; nums.pop(i+1); break
                if len(nums)!=want:
                    issues.append((sec,model,f'n={len(nums)} want={want} raw={raw}'))
                    continue
                vals=[float(x) for x in nums]
                # 绕组/pmg/出线 元数据
                toks=l[mm.end():].split()
                j=0; wind=''
                if toks and WIND_RE.fullmatch(toks[0]): wind=toks[0]; j+=1
                pmg=''
                if j<len(toks) and toks[j] in ('可选','标配'): pmg=toks[j]; j+=1
                wires=''
                if j<len(toks) and toks[j] in ('12','6','4','12/6','6/12'): wires=toks[j]; j+=1
                rec={'sec':sec,'model':model,'frequency':('50Hz' if sec.startswith('8') else '60Hz'),
                     'winding':wind,'pmg':pmg,'wires':wires,'pf':0.8,'groups':[]}
                idx=0
                for g in range(ng):
                    grp={'voltage':groups[g],'ratings':{}}
                    for r in range(3):
                        kw,kva=vals[idx],vals[idx+1]; idx+=2
                        grp['ratings'][RATING_KEYS[r]]={'kW':kw,'kVA':kva}
                    rec['groups'].append(grp)
                records.append(rec)
    return records, issues

if __name__=='__main__':
    recs,issues=parse()
    print(f"成功: {len(recs)}  问题: {len(issues)}")
    from collections import Counter
    c=Counter(r['sec'] for r in recs)
    for s,n in sorted(c.items(),key=lambda x:(x[0].split('.')[0],int(x[0].split('.')[1]))):
        print(f"  {s}: {n}")
    if issues:
        print("\n--- 问题 ---")
        for sec,m,msg in issues[:20]: print(f"  [{sec}] {m}: {msg}")
    json.dump(recs,open('/tmp/agg_ki_records.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
    print("\n已存 /tmp/agg_ki_records.json")
