"""Render saved results and deterministic contribution audit, without new inference."""
from pathlib import Path
import sys, json
import numpy as np
import pandas as pd
import rasterio
from scipy import ndimage
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
from analysis.physical_constraints import sha256_file
from analysis.phase3b_references import load_raw_reference
from analysis.rcm_preprocessing import CommonGrid
from scripts.phase3b_pipeline import permanent_and_egs_masks
from scripts.phase3b_rf import _scene_info

BASE=ROOT/'data/processed/phase3b';OUT=BASE/'rf_v2_final';grid=CommonGrid()
rows=[]
fig,axes=plt.subplots(1,5,figsize=(15,4.2),layout='constrained')
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
for index,(sid,row) in enumerate(_scene_info().iterrows()):
 with rasterio.open(OUT/'masks'/f'{sid}_flood.tif') as ds: final=ds.read(1)==1
 with rasterio.open(OUT/'masks'/f'{sid}_reason_codes.tif') as ds: codes=ds.read(1)
 normal=(codes&1)>0; lab,n=ndimage.label(normal,np.ones((3,3)));sizes=np.bincount(lab.ravel(),minlength=n+1)
 base=(lab>0)&(sizes[lab]>=4); ordinary=(codes&8)>0; small=(codes&16)>0
 raw,valid,_=load_raw_reference(BASE/'references/raw_egs_30m'/f'{sid}.geojson',grid)
 _,legacy=permanent_and_egs_masks(row.egs_observation_id)
 for rid,reference in [('primary_raw_egs_reference',raw),('legacy_phase4_reference',legacy)]:
  for name,mask in [('terrain_net_additions',ordinary&~base),('terrain_net_removals',base&~ordinary),('small_component_additions',small),('final_vs_rf_v1_net_additions',final&~base)]:
   mask &=valid
   rows.append(dict(observation_id=sid,reference_id=rid,contribution=name,pixels=int(mask.sum()),tp_pixels=int((mask&reference).sum()),fp_pixels=int((mask&~reference).sum()),area_ha=float(mask.sum()*.09)))
 image=final.astype('uint8')+2*raw.astype('uint8')
 axes[index].imshow(image,cmap=ListedColormap(['#f1f1f1','#0072B2','#D55E00','#009E73']),vmin=0,vmax=3)
 axes[index].set_title(sid[:8]+' UTC');axes[index].axis('off')
fig.legend(handles=[Patch(color=c,label=l) for c,l in [('#009E73','TP'),('#0072B2','FP'),('#D55E00','FN')]],loc='lower center',ncol=3)
fig.suptitle('Frozen RF v2 vs original EGS class 2 — 30 m, no raster shift')
fig.savefig(OUT/'qa/final_disagreement.png',dpi=130);plt.close(fig)
pd.DataFrame(rows).to_csv(OUT/'final_contribution_audit.csv',index=False)
# Archive a minimal reproducible numerical research record, not every scratch table.
research=Path('/tmp/phase3b-convergence-05meMh')
for name in ['geometry_summary.csv','geometry_notes.json']:
 p=research/name
 if p.exists(): (OUT/'qa'/('archived_'+name)).write_bytes(p.read_bytes())
manifest=json.loads((OUT/'final_run_manifest.json').read_text())
manifest['artifacts']={str(p.relative_to(BASE)):sha256_file(p) for p in OUT.rglob('*') if p.is_file() and p.name!='final_run_manifest.json'}
manifest['report_postprocessing']='saved-mask diagnostics and QA rendering only; no retraining, new classifier evaluation or retuning'
(OUT/'final_run_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
print(pd.DataFrame(rows).groupby(['reference_id','contribution'])[['pixels','tp_pixels','fp_pixels']].sum().to_string())

