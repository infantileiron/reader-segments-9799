import {state} from '../stores/session.js';import {esc} from '../utils/html.js';import {table} from '../components/common/table.js';import {field} from '../components/common/fields.js';import {badge} from '../components/common/status.js';import {EVENT_STATES,SUMMARY_STATES} from '../constants/enums.js';
const pct=x=>x===null||x===undefined?'—':(x*100).toFixed(1)+'%';
const tm=x=>esc(String(x).replace('T',' ').replace('+08:00',''));
const mins=w=>Math.round(w/60)+'分钟';
function intervals(list){return list?.length?`<ul class="iv">${list.map(([s,e])=>`<li>${tm(s)} → ${tm(e)}</li>`).join('')}</ul>`:'<p>无。</p>'}
function detail(w){
 if(!w||!w.detail)return '';
 let d=w.detail;
 return `<div class="notice"><h3>#${w.id} ${esc(w.code)} · ${esc(w.week)} 起自然周 · ${SUMMARY_STATES[w.state]||w.state}</h3>
 <p>有效事件 ${d.active_events} 条 · 撤销 ${d.revoked_events} 条 · 全部时段并集 ${mins(d.total_seconds)} · 夜读时段并集 ${mins(d.night_seconds)}</p>
 <h3>时段合并（跨设备重叠只计一次）</h3>${intervals(d.merged)}
 <h3>夜读时段 22:00–06:00</h3>${intervals(d.night)}
 <h3>各文章最高完读比例</h3>${d.articles?.length?`<ul class="iv">${d.articles.map(a=>`<li>${esc(a.article)} · ${(a.ratio*100).toFixed(0)}%</li>`).join('')}</ul>`:'<p>无。</p>'}
 ${d.revoked?.length?`<h3>撤销依据</h3><ul class="iv">${d.revoked.map(r=>`<li>${esc(r.event_id)} · ${esc(r.reason)}</li>`).join('')}</ul>`:''}</div>`}
export function render(){
 const open=state.summaries.find(w=>w.id===state.detailId);
 const rows=state.summaries.map(w=>`<tr><td>${esc(w.code)}</td><td>${esc(w.week)}</td><td>${badge(SUMMARY_STATES[w.state]||w.state)}</td><td>${w.weekly_reading??'—'}</td><td>${pct(w.completion)}</td><td>${pct(w.night_share)}</td><td class="act">${w.state==='pending'?`<button data-compute="${esc(w.code)}|${esc(w.week)}">计算</button>`:''}${w.state==='computed'?`<button data-publish="${w.id}">发布</button>`:''}<button data-summary="${w.id}">${state.detailId===w.id?'收起':'详情'}</button></td></tr>`).join('');
 return `<div class="split"><section class="panel"><h2>阅读事件与周汇总</h2><p>事件带唯一编号，重试不重复计入；撤销为先到先生效的墓碑，原事件后到也不复活。按北京时间自然周裁剪时段，篇数按文章去重，完读率取各文章最高比例的均值，夜读占比为22:00–06:00时段并集 ÷ 全部时段并集，零时长留空。汇总经待计算→已计算→已发布后才会进入阅读档案，分群取数只见已发布口径。</p>
 <div class="result-head"><h3>周汇总</h3><button id="compute-all">计算全部待计算</button></div>
 <div class="scroll"><table><thead><tr><th>会员</th><th>自然周</th><th>状态</th><th>篇数</th><th>完读率</th><th>夜读占比</th><th>操作</th></tr></thead><tbody>${rows||'<tr><td>尚无汇总。录入首条阅读事件后自动生成待计算汇总。</td></tr>'}</tbody></table></div>
 ${open?detail(open):''}
 <h3>事件流水</h3>${table(['事件编号','会员','文章','开始','结束','完读比例','状态','撤销依据'],state.events.map(e=>[e.event_id,e.code,e.article,String(e.start).replace('T',' ').replace('+08:00',''),String(e.end).replace('T',' ').replace('+08:00',''),(e.ratio*100).toFixed(0)+'%',EVENT_STATES[e.state]||e.state,e.revoke_reason||'—']))}
 </section><aside class="side"><h2>录入阅读事件</h2><form id="event">${field('事件编号（幂等键）','event_id','text','required placeholder="EVT-20261110-001"')}${field('会员编号','code','text','required placeholder="SL-001"')}${field('文章编号','article','text','required placeholder="A-101"')}${field('开始时间（北京时间）','start','datetime-local','required')}${field('结束时间（北京时间）','end','datetime-local','required')}${field('完读比例 / 0–1','ratio','number','min=0 max=1 step=0.01 required')}<button class="primary">接收事件</button></form>
 <h2>撤销事件</h2><form id="revoke">${field('事件编号','event_id','text','required')}<label>撤销依据<textarea name="reason" rows="2" minlength="2" required placeholder="例如：设备时钟异常，运营复核后撤销"></textarea></label><button class="primary">登记撤销</button></form>
 <p>撤销先到：原事件后到或重试都保持已撤销。重复撤销保留首个依据。</p></aside></div>`}
