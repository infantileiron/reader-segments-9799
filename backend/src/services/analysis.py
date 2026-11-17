import json,hashlib
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
FEATURES=['weekly_reading','completion','night_share']
SEED=3107
def cluster(rows,features,k):
 if len(features)<2 or len(set(features))!=len(features) or not set(features)<=set(FEATURES):raise ValueError('选择2–3个不同的有效特征')
 if k<2 or k>6:raise ValueError('分群数仅支持2–6')
 if len(rows)<=k:raise ValueError('样本数必须大于分群数，补充会员档案或降低k')
 x=np.array([[r[f] for f in features] for r in rows],dtype=float)
 if not np.isfinite(x).all():raise ValueError('特征包含缺失或非有限值，请先修订档案')
 if np.any(np.ptp(x,axis=0)<=1e-12):raise ValueError('所选特征中存在常量列，请移除该特征或补充有差异的样本')
 if len(np.unique(x,axis=0))<k:raise ValueError('不同特征点少于k，不能形成指定数量的群组')
 scaler=StandardScaler();z=scaler.fit_transform(x);model=KMeans(n_clusters=k,random_state=SEED,n_init=20,algorithm='lloyd');labels=model.fit_predict(z)
 if len(set(labels))!=k:raise ValueError('实际群数小于k，请检查重复点或降低k')
 centers=scaler.inverse_transform(model.cluster_centers_)
 order=sorted(range(k),key=lambda i:tuple(centers[i]));mapping={old:new for new,old in enumerate(order)}
 memberships=[dict(id=r['id'],code=r['code'],cluster_id=mapping[int(label)],**{f:r[f] for f in FEATURES},x=float(point[0]),y=float(point[1])) for r,label,point in zip(rows,labels,z)]
 profiles=[]
 for old in order:
  members=[r for r in memberships if r['cluster_id']==mapping[old]]
  profiles.append(dict(cluster_id=mapping[old],size=len(members),portrait={f:float(np.mean([r[f] for r in members])) for f in FEATURES},center_inverse={f:float(v) for f,v in zip(features,centers[old])},member_codes=[r['code'] for r in members]))
 return dict(n=len(rows),k=k,features=features,profiles=profiles,members=memberships,silhouette=float(silhouette_score(z,labels)),inertia=float(model.inertia_),scaler_mean=scaler.mean_.tolist(),scaler_scale=scaler.scale_.tolist(),seed=SEED,checksum=hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),method='StandardScaler总体均值/标准差→KMeans欧氏距离，n_init=20、seed=3107；群号按原始中心排序，便于同一版本复核；轮廓系数用标准化空间。分群是行为相似性，不是会员价值或因果判断。')
