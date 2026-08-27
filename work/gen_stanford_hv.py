#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STAMFORD Edition9 中高压 -> 生成 stanford-hv.json
字段口径(与 stanford.json 一致):
  stdby_27c = 163/27  备用27℃
  stdby_40c = 150/40  备用40℃
  cont_h    = 125/40(H) 持续H
  cont_f    = 105/40(F) F级
  cont_b    = 80/40(B)  B级
附加: temp_grade(主用温升档=F,中高压按F级选型), winding_id(绕组号), pitch(节距),
      freq_seg 等。
"""
import json, re, subprocess, sys

PDF="/Users/bob/.openclaw/media/inbound/STAMFORD_Industrial_Ratings_Book_Edition_9---92dde791-e1aa-4b86-84ee-84f908ef5218.pdf"

def page_text(p):
    r=subprocess.run(['pdftotext','-f',str(p),'-l',str(p),'-layout',PDF,'-'],
                     capture_output=True,text=True)
    return r.stdout

# ---------- 解析单页为区段/绕组块 ----------
def parse_page(p):
    lines=page_text(p).split('\n')
    starts=[i for i,l in enumerate(lines) if re.search(r'4 POLE (Medium Voltage|High Voltage|Three Phase)',l)]
    secs=[]
    for s in starts:
        sec={'page':p,'freq':None,'volt':None,'blocks':[]}
        for i in range(s,min(s+12,len(lines))):
            m=re.search(r'(50Hz|60Hz)\s*/\s*(\d+)rpm',lines[i])
            if m and not sec['freq']: sec['freq']=m.group(1); break
        sec_end=starts[starts.index(s)+1] if starts.index(s)+1<len(starts) else len(lines)
        for i in range(s,min(sec_end,s+14)):
            if 'Star' in lines[i]:
                v=lines[i].replace('Star','').strip().replace(' ','').replace('\u00a0','')
                if re.search(r'\d+V',v): sec['volt']=v; break
                for j in range(i+1,min(sec_end,i+4)):
                    m2=re.match(r'^\s*([\d\.]+V-?[\d\.]*V?)\s',lines[j]) or re.match(r'^([\d\.]+V-?[\d\.]*V?)$',lines[j].strip())
                    if m2:
                        sec['volt']=m2.group(1).replace(' ','').replace('\u00a0',''); break
                if sec['volt']: break
        wi=[i for i in range(s,sec_end) if lines[i].strip()=='Winding']
        for k,w0 in enumerate(wi):
            blk={}
            m=re.match(r'^\s*([\d]+)\s*\((\d/\d)\s*Pitch\)',lines[w0+1].strip())
            if not m: continue
            blk['wind']=m.group(1); blk['pitch']=m.group(2)
            dend=wi[k+1] if k+1<len(wi) else sec_end
            mrow=None
            for i in range(w0+1,min(dend,w0+9)):
                if 'Model' in lines[i]: mrow=i; break
            rows=[]
            if mrow is not None:
                for i in range(mrow+1,dend):
                    s2=lines[i].strip()
                    if not s2: continue
                    if s2=='Winding': break
                    if re.match(r'^\d+ +- ',s2) or 'Available in' in s2 or re.search(r'V Rating',s2): break
                    if re.search(r'\d',s2) and not s2.startswith('Model'):
                        rows.append(lines[i].rstrip())
            blk['rows']=rows
            sec['blocks'].append(blk)
        if sec['volt'] and sec['freq']:
            # 中高压过滤: 电压最低3300V; 低于1000V(低压)排除; Three Phase页(如12470V)纳入
            try:
                vmin=int(re.search(r'(\d+)\s*V',sec['volt']).group(1))
            except Exception:
                vmin=0
            if vmin>=1000:
                secs.append(sec)
    return secs

# ---------- 解析数据行 ----------
# 行格式: 型号 [注记] vA vkW vB vkW ... (5档=10个数)
# 型号含 P80(双词) 如 "P80 MVSI804R"; 注记如 "2"、"2,&"、"#/&"
def parse_row(line):
    parts=line.split()
    if not parts: return None
    # 型号: 可能是单词或 "P80 XXXX"
    if parts[0]=='P80' and len(parts)>=3 and parts[1].isdigit()==False and re.match(r'[A-Z0-9]',parts[1]):
        # P80 开头，型号为两词
        model='P80 '+parts[1]; rest=parts[2:]
    else:
        model=parts[0]; rest=parts[1:]
    # 从尾部取 10 个数值 token(含 N/A)
    nums=[]; note_tokens=[]
    j=len(rest)-1
    while j>=0 and len(nums)<10:
        x=rest[j]
        if x=='N/A': nums.append(None)
        elif re.fullmatch(r'[\d\.]+',x): nums.append(float(x))
        else: break
        j-=1
    if len(nums)!=10:
        return None
    nums.reverse()
    # 剩余 token 全部是注记
    note=' '.join(rest[:j+1]).replace(' ','').replace(',',',') if j>=0 else ''
    return {'model':model,'note':note,'vals':nums}

# 5档索引: 0=stdby27 1=stdby40 2=contH 3=contF 4=contB (每档kVA,kW)
def to_record(freq, volt, blk, row):
    vals=row['vals']
    def v(idx):  # idx 0..4
        kv=vals[idx*2]; kw=vals[idx*2+1]
        return (kv,kw)
    s27,s40,ch,cf,cb=v(0),v(1),v(2),v(3),v(4)
    rec={
      'type':'generator','brand':'斯坦福中高压','model':row['model'],
      'frequency':freq,
      'wind_volt':volt,
      'winding_id':blk['wind'],
      'pitch':blk['pitch'],
      'winding_code': volt+'-W'+blk['wind'],
      'pf':0.8,'poles':4,
      'note':row['note'] or None,
      'temp_grade':'F',   # 中高压按F级温升选型
    }
    # 5 档功率(有 N/A 则省略键)
    fields=[('stdby_27c',s27),('stdby_40c',s40),('cont_h',ch),('cont_f',cf),('cont_b',cb)]
    for key,(kv,kw) in fields:
        if kv is not None and kw is not None:
            rec[key+'_kVA']=kv; rec[key+'_kW']=kw
    return rec

# ---------- 主流程 ----------
all_recs=[]
for p in range(66,86):
    for sec in parse_page(p):
        for blk in sec['blocks']:
            for rowraw in blk['rows']:
                row=parse_row(rowraw)
                if row is None:
                    print(f'!! 无法解析行 p{p} {sec["volt"]} W{blk["wind"]}: |{rowraw.strip()[:60]}|',file=sys.stderr)
                    continue
                rec=to_record(sec['freq'],sec['volt'],blk,row)
                all_recs.append(rec)

print('原始记录数:',len(all_recs))
# 去重: (frequency, wind_volt, winding_id, model, note) 去重
# note 含电压细分(#/&)时必须区分: 6600V-6900V 的 #=6600V &amp;=6900V
seen=set(); dedup=[]
for r in all_recs:
    k=(r['frequency'],r['wind_volt'],r['winding_id'],r['model'],r['note'] or '')
    if k in seen: 
        print('  去重:',k)
        continue
    seen.add(k); dedup.append(r)
print('去重后:',len(dedup))

# 保存中间结果
with open('/tmp/stanford_hv_records.json','w') as f:
    json.dump(dedup,f,ensure_ascii=False,indent=1)
print('已存 /tmp/stanford_hv_records.json')
# 概要
from collections import Counter
print('电压×频率 分布(型号数):')
cv=Counter((r['wind_volt'],r['frequency']) for r in dedup)
for (v,f),n in sorted(cv.items(),key=lambda x:(x[0][1],int(re.search(r'\d+',x[0][0]).group()))):
    print(f'  {v} [{f}]: {n}型号')
