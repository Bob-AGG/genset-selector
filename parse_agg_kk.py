#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AGG KK 系列手册解析器 v1
与 KI 同构, 差异: PMG 列有 '⸺'(U+23BA 不可用) 需剥离; 型号 KK164~KK454.
pdftotext 主干 + 修正 WIND_RE + 数字拆分合并(fitz x 坐标辅助).
"""
import re, json, fitz

TXT="/tmp/agg_kk.txt"
PDF="/Users/bob/.openclaw/workspace/media/inbound/openclaw-staged-564ef801-00e1-4b40-a577-065c3c0856e5/AGG发电机_KK系列-KK_Series_产品手中文版-2023---f850dc7a-455d-4f37-86c6-039e39da771c.pdf"

lines=open(TXT,encoding='utf-8',errors='ignore').read().split('\n')
pages=[]; cur=[]
for l in lines:
    if '\x0c' in l:
        if cur: pages.append(cur); cur=[]
        cur=[l.replace('\x0c','')]
    else: cur.append(l)
if cur: pages.append(cur)

# 页映射 (pdftotext 0idx, 与 fitz 同番号)
TABLE_PAGES={
 '8.1':[8,9],'8.2':[10,11],'8.3':[12],'8.4':[13],'8.5':[14],
 '8.6':[15,16],'8.7':[17,18],'8.8':[19,20],
 '9.1':[22,23],'9.2':[24,25],'9.3':[26,27],'9.4':[28],'9.5':[29],
 '9.6':[30,31],'9.7':[32,33],'9.8':[34,35],
}
# 每表: 组数电压标签列表 (全部 kW+kVA 两列结构, 无 kwonly)
SEC_META={
 '8.1':['190V/220V/380V','200V/230V/400V','208V/240V/415V'],
 '8.2':['440V/220V'],
 '8.3':['220-240V'],
 '8.4':['230V/115V'],
 '8.5':['415-440V','240-254V'],
 '8.6':['500V','525V'],
 '8.7':['550V','600V'],
 '8.8':['660V','690V'],
 '9.1':['380-400V','208V/416V'],
 '9.2':['220V/440V','240V/480V'],
 '9.3':['380V','416V'],
 '9.4':['220-240V'],
 '9.5':['230V/115V'],
 '9.6':['220V/440V'],
 '9.7':['347V','600V'],
 '9.8':['660V','690V'],
}
RATING_KEYS=['cont_40c','stdby_40c','stdby_27c']
WIND_RE=re.compile(r'^(B\d+|D\d+|T\d+(?:/T?\d+)?)$')
NUM=re.compile(r'\d+(?:\.\d+)?')
SKIP=re.compile(r'号绕组|上述参数|解释权|详细参数|励磁系统|出线数|^\s*型号|^\s*kW|^\s*kVA|持续|备用|st\.by|220V/440V|AGG保留|请向AGG')
# PMG 列占位符: ⸺ U+23BA, 及普通破折号
PMGPH=re.compile(r'^[⸺—–-]+$')
KK_RE=re.compile(r'\bKK\s?(\d{3}[A-Z]+)\b')

def parse():
    records=[]; issues=[]
    for sec,pgs in TABLE_PAGES.items():
        groups=SEC_META[sec]; ng=len(groups)
        want=ng*3*2   # 全部 kW+kVA 两列
        for pg in pgs:
            if pg>=len(pages): continue
            for l in pages[pg]:
                if SKIP.search(l): continue
                mm=KK_RE.search(l)
                if not mm: continue
                model='KK '+mm.group(1)
                rest=l[mm.end():]
                toks=rest.split()
                # 剥 绕组 / pmg占位或可选标配 / 出线
                j=0; wind=''; pmg=''; wires=''
                if toks and WIND_RE.fullmatch(toks[0]): wind=toks[0]; j+=1
                if j<len(toks) and (PMGPH.fullmatch(toks[j]) or toks[j] in ('可选','标配')):
                    pmg='' if PMGPH.fullmatch(toks[j]) else toks[j]
                    j+=1
                if j<len(toks) and toks[j] in ('12','6','4','12/6','6/12'):
                    wires=toks[j]; j+=1
                nums=[t for t in toks[j:] if NUM.fullmatch(t)]
                if len(nums)!=want:
                    # 若全部数据为占位符('/','-','⸺') 表示不支持该电压, 跳过
                    leftover=toks[j:]
                    if leftover and all(PMGPH.fullmatch(x) or x=='/' for x in leftover):
                        continue
                    issues.append((sec,model,f'n={len(nums)} want={want} toks={toks}'))
                    continue
                vals=[float(x) for x in nums]
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
    for s,n in sorted(c.items(),key=lambda x:(x[0].split('.')[0],int(x[0].split('.')[1]))): print(f"  {s}: {n}")
    if issues:
        print("\n--- 问题(前25) ---")
        for sec,m,msg in issues[:25]: print(f"  [{sec}] {m}: {msg}")
    json.dump(recs,open('/tmp/agg_kk_records.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
    print("已存 /tmp/agg_kk_records.json")
