#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AGG KI/KK 格式转换: 手册多电压组 -> 前端 BRAND_FILES 单条格式
映射:
  cont_h     = 持续125K/40°C
  cont_f     = AGG无第二持续值 -> 0(前端 ||0 处理)
  stdby_40c  = 备用150K/40°C
  stdby_27c  = 备用163K/27°C
  exc_std    = 'SHUNT'(自励)
  exc_opt    = 'PMG'(手册标可选/标配)
  winding_code = '<绕组>-<主电压>' 例 'B31-400'; 单相 '<绕组>-1ph-230'
  winding_label = 完整电压组串, 例 '190V/220V/380V'
  单相(kVA=kW) 用 1ph 标记
"""
import json, re

def main_voltage(label):
    """取电压组串里的主电压(首选380/400/415/440/230/500...): 取第一个或在列"""
    volts=re.findall(r'(\d{3})', label)
    pref=['415','400','380','440','480','550','525','500','600','660','690','690','230','240','220','115','120','416','347']
    if not volts: return ''
    v=volts[0]
    for p in pref:
        if p in volts: v=p; break
    return v

def is_single_phase(sec):
    # 真单相绕组(手册 pf=1, kVA=kW): KI 8.6(D51)/9.7(D61); KK 8.4(D51)/9.5(D61)
    sp={'8.6','9.7'} if True else set()
    # 用系列区分
    return sec in {'8.6','9.7'} or sec in {'8.4','9.5'}

# 实际用 kVA==kW 判定最稳: 由调用方传入评分值判断
TRUE_1PH_KI={'8.6','9.7'}
TRUE_1PH_KK={'8.4','9.5'}

def convert(records, brand):
    # 判定该系列真单相表(手册 pf=1, kVA=kW)
    if brand=='AGG KI': true1ph={'8.6','9.7'}
    else: true1ph={'8.4','9.5'}
    out=[]
    for r in records:
        sec=r['sec']; freq=r['frequency']
        for gi,g in enumerate(r['groups']):
            vals=g['voltage']
            ratings=g['ratings']
            sp=sec in true1ph
            wind=r['winding']
            mv=main_voltage(vals)
            wcode = wind+'-'+mv if not sp else wind+'-1ph-'+mv
            rec={
                'type':'generator',
                'brand':brand,
                'model':r['model'],           # 'KI 164A' 带空格
                'frequency':freq,
                'winding_code':wcode,
                'winding_label':vals,
                'wires':r.get('wires') or '',
                'pf':1.0 if sp else 0.8,
                'exc_std':'SHUNT',
                'exc_opt':'PMG' if r.get('pmg') in ('可选','标配') else '',
                'cont_h_kVA':ratings['cont_40c']['kVA'],
                'cont_h_kW':ratings['cont_40c']['kW'],
                'cont_f_kVA':0, 'cont_f_kW':0,
                'stdby_40c_kVA':ratings['stdby_40c']['kVA'],
                'stdby_40c_kW':ratings['stdby_40c']['kW'],
                'stdby_27c_kVA':ratings['stdby_27c']['kVA'],
                'stdby_27c_kW':ratings['stdby_27c']['kW'],
            }
            out.append(rec)
    return out

if __name__=='__main__':
    import sys
    for src,brand,outf in [('/tmp/agg_ki_records.json','AGG KI','agg-ki.json'),
                            ('/tmp/agg_kk_records.json','AGG KK','agg-kk.json')]:
        recs=json.load(open(src,encoding='utf-8'))
        conv=convert(recs,brand)
        json.dump(conv,open(outf,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
        print(f"{outf}: {len(recs)} 源 -> {len(conv)} 转换 | 品牌={brand}")
