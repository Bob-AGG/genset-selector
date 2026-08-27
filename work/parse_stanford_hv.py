#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析 STAMFORD Edition 9 中高压 (物理页 66-85)。用按页 pdftotext 避免全文串扰。
按电压区段+绕组块解析，同(电压,绕组,节距)自动去重。输出 JSON。
"""
import json, re, subprocess, sys, os

PDF="/Users/bob/.openclaw/media/inbound/STAMFORD_Industrial_Ratings_Book_Edition_9---92dde791-e1aa-4b86-84ee-84f908ef5218.pdf"
PAGES=range(66,86)  # 66-85

def page_text(p):
    r=subprocess.run(['pdftotext','-f',str(p),'-l',str(p),'-layout',PDF,'-'],
                     capture_output=True,text=True)
    return r.stdout

# 逐页收集原始区段
all_secs=[]  # 每个: {page, freq, volt, blocks:[{wind,pitch,rise,rows}]}
for p in PAGES:
    txt=page_text(p)
    lines=txt.split('\n')
    # 找区段起始(4 POLE Medium/High Voltage) — 一页可有多区段(如Page80有7200V+11000V)
    starts=[i for i,l in enumerate(lines) if re.search(r'4 POLE (Medium|High|Three Phase) Voltage',l) or re.search(r'4 POLE (Medium|High) Voltage',l)]
    for s in starts:
        sec={'page':p,'freq':None,'volt':None,'blocks':[]}
        # 频率 (Page75 特殊: Star 行即含频率; 一般在后)
        for i in range(s,min(s+12,len(lines))):
            m=re.search(r'(50Hz|60Hz)\s*/\s*(\d+)rpm',lines[i])
            if m and not sec['freq']: sec['freq']=m.group(1); break
        # 电压: Star 行(可能电压在 Star 下一行，如 Page75 的 10500V-11000V)
        sec_end = starts[starts.index(s)+1] if starts.index(s)+1<len(starts) else len(lines)
        for i in range(s,min(sec_end, s+14)):
            if 'Star' in lines[i]:
                v=lines[i].replace('Star','').strip().replace(' ','').replace('\u00a0','')
                if re.search(r'\d+V',v): sec['volt']=v; break
                # 电压在下一行
                for j in range(i+1,min(sec_end,i+4)):
                    v2=lines[j].strip()
                    m2=re.match(r'^\s*([\d\.]+V-?[\d\.]*V?)\s', v2) or re.match(r'^([\d\.]+V-?[\d\.]*V?)$', v2)
                    if m2:
                        sec['volt']=m2.group(1).replace(' ','').replace('\u00a0',''); break
                if sec['volt']: break
        # 绕组块
        wi=[i for i in range(s,sec_end) if lines[i].strip()=='Winding']
        for k,w0 in enumerate(wi):
            blk={}
            hdr=lines[w0+1].strip()
            m=re.match(r'^\s*([\d]+)\s*\((\d/\d)\s*Pitch\)',hdr)
            if not m: 
                print(f'!! page{p} 绕组头解析失败: |{hdr}|',file=sys.stderr); continue
            blk['wind']=m.group(1); blk['pitch']=m.group(2)
            blk['rise']=lines[w0+2].strip()
            dend=wi[k+1] if k+1<len(wi) else sec_end
            mrow=None
            for i in range(w0+1,min(dend,w0+9)):
                if 'Model' in lines[i]: mrow=i; break
            rows=[]
            if mrow is not None:
                for i in range(mrow+1,dend):
                    l=lines[i]; s2=l.strip()
                    if not s2: continue
                    if s2=='Winding': break
                    if re.match(r'^\d+ +- ',s2) or 'Available in' in s2 or re.search(r'V Rating',s2): break
                    if re.match(r'^(P?\d?[A-Z0-9]+\s+|S\dH1D|S\dM1D|UCI|HCI|P80|S[0-9])',s2) and not s2.startswith('Model'):
                        rows.append(s2)
            blk['rows']=rows
            sec['blocks'].append(blk)
        if sec['volt'] and (sec['freq']):
            all_secs.append(sec)
        else:
            print(f'!! page{p} 缺少电压/频率, 跳过',file=sys.stderr)

# 打印概况
print(f'共 {len(all_secs)} 个区段:')
for sc in all_secs:
    print(f"  Page{sc['page']} [{sc['freq']}] {sc['volt']}: "+', '.join(f"W{b['wind']}({b['pitch']})×{len(b['rows'])}" for b in sc['blocks']))
