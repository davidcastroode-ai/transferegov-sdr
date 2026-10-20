
// ===================== cartões clicáveis: clicar num cartão mostra a lista do que ele soma =====================
// a página preenche KPI_DEF[chave] = {tit, lista, cols} a cada render e marca o cartão com data-kpi="chave"
var KPI_DEF = window.KPI_DEF || {}; window.KPI_DEF = KPI_DEF;
function kpiDepois(){
  document.querySelectorAll('[data-kpi]').forEach(c => { c.classList.add('kpi-cl'); c.classList.toggle('kpi-on', c.dataset.kpi === window.__kpi); });
  let box = document.getElementById('kpLista');
  if(!box){ const ref = document.querySelector('[data-kpi]'); if(!ref) return; const grade = ref.closest('.kp') || ref.parentElement;
    box = document.createElement('div'); box.id = 'kpLista'; grade.parentNode.insertBefore(box, grade.nextSibling); }
  // a caixa fica logo abaixo da fileira do cartão clicado
  const on = window.__kpi && document.querySelector(`[data-kpi="${window.__kpi}"]`);
  if(on){ const grade = on.closest('.kp') || on.parentElement; if(grade.nextSibling !== box) grade.parentNode.insertBefore(box, grade.nextSibling); }
  const d = window.__kpi && (window.KPI_DEF||{})[window.__kpi];
  if(!d){ box.innerHTML = ''; return; }
  if(KF.__on !== window.__kpi) KF = {__on: window.__kpi};
  const foco = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.kf : null;
  const LF = kpiFiltrar(d.lista), cols = kpiCols(d), fil = LF.length !== d.lista.length;
  const uniq = a => [...new Set(a)].filter(x => x && x !== '—');
  const mods = uniq(d.lista.map(o => kTipo(o)[0])).sort(), anos = uniq(d.lista.map(o => String(o.ano||''))).sort().reverse();
  const fins = uniq(d.lista.map(kFin));
  const sel = (k, vals, rot) => `<label>${rot}<select data-kf="${k}"><option value="">Todos</option>${vals.map(v => `<option${KF[k]===v?' selected':''}>${esc(v)}</option>`).join('')}</select></label>`;
  const finOps = fins.length ? ['EXE','RAP','EXE e RAP'].concat(fins.filter(v => !/EXE|RAP/.test(v))) : [];
  const met = kpiMetrica(d, cols);
  let pill = '';
  if(met){ const vF = LF.reduce((a,o) => a + met(o), 0), vT = d.lista.reduce((a,o) => a + met(o), 0);
    pill = `<span class="kpi-res${fil?' fil':''}" title="${esc(kBRL(vF))}${fil ? ' de '+esc(kBRL(vT)) : ''}">${fil ? 'Filtrado' : 'Total'}: <b>R$ ${fm(vF)}</b>${fil ? ' de '+fm(vT) : ''}</span>`; }
  else pill = `<span class="kpi-res${fil?' fil':''}">${fil ? 'Filtrado' : 'Total'}: <b>${LF.length.toLocaleString('pt-BR')}</b>${fil ? ' de '+d.lista.length.toLocaleString('pt-BR') : ''}</span>`;
  const limpa = Object.keys(KF).some(k => k !== '__on' && KF[k]) ? '<button type="button" class="kpi-bt" data-kflimpa="1">Limpar</button>' : '';
  box.innerHTML = `<section class="card kpi-box"><div class="kpi-cab"><div><h3>📋 ${esc(d.tit)}</h3><p class="d">${fil ? LF.length.toLocaleString('pt-BR')+' de ' : ''}${d.lista.length.toLocaleString('pt-BR')} registro(s) · clique na linha para abrir a ficha</p></div>
    <div><button type="button" class="kpi-bt" data-kpicsv="1">⬇ Baixar lista (CSV)</button><button type="button" class="kpi-bt" data-kpifecha="1">✕ Fechar</button></div></div>
    <div class="kpi-fil"><label>Instrumento<input type="search" data-kf="q" value="${esc(KF.q||'')}" placeholder="nº, proponente…"></label>
    ${mods.length ? sel('mod', mods, 'Modalidade') : ''}${finOps.length ? sel('fin', finOps, 'Financeiro') : ''}${anos.length ? sel('ano', anos, 'Ano') : ''}${limpa}${pill}</div>
    ${tabela('k', LF, cols, 10)}</section>`;
  if(foco){ const x = box.querySelector(`[data-kf="${foco}"]`); if(x){ x.focus(); if(x.type === 'search'){ const n = x.value.length; try{ x.setSelectionRange(n, n); }catch(e){} } } }
}
// ---- filtros, modalidade, financeiro (EXE/RAP) e resumo em valor: mesmo padrão do painel de Parcerias
var KF = {};
const kBRL = v => 'R$ '+Number(v||0).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
function kTipo(o){ const m = String(o && o.mod || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
  return /FOMENTO/.test(m) ? ['Termo de Fomento','#2e7d32'] : /REPASSE/.test(m) ? ['Contrato de Repasse','#b8650a'] : /COLABORA/.test(m) ? ['Termo de Colaboração','#6a3d9a'] : /CONVENIO/.test(m) ? ['Convênio','#1f4e79'] : m ? [o.mod,'#666'] : ['—','']; }
function kFin(o){
  if(o && o.sE !== null && o.sE !== undefined){ const e = (o.sE||0) > 0.005, r = (o.sR||0) > 0.005; return e && r ? 'EXE e RAP' : e ? 'EXE' : r ? 'RAP' : 'Sem saldo'; }
  const anos = (o && o.nes || []).map(x => { const t = Array.isArray(x) ? x.find(v => /^\d{4}NE/.test(String(v))) : x; return +((String(t||'').match(/^(\d{4})NE/)||[])[1]||0); }).filter(Boolean);
  if(!anos.length) return '—';
  const a = new Date().getFullYear(), e = anos.includes(a), r = anos.some(x => x < a);
  return e && r ? 'EXE e RAP' : e ? 'EXE' : 'RAP';
}
function kpiFiltrar(L){
  const q = String(KF.q||'').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
  const norm = v => String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
  return L.filter(o => (!q || norm([o.n, o.num, o.prop, o.parl, o.munN, o.objr, o.ent].join(' ')).includes(q))
    && (!KF.mod || kTipo(o)[0] === KF.mod)
    && (!KF.fin || (KF.fin === 'EXE' ? /EXE/.test(kFin(o)) : KF.fin === 'RAP' ? /RAP/.test(kFin(o)) : kFin(o) === KF.fin))
    && (!KF.ano || String(o.ano||'') === KF.ano));
}
const kTag = (t, c) => `<span style="display:inline-block;background:${c};color:#fff;font-size:10.5px;font-weight:700;padding:1px 8px;border-radius:10px;white-space:nowrap">${esc(t)}</span>`;
function kpiCols(d){
  let c = d.cols.slice();
  if(d.lista.some(o => o.mod) && !c.some(x => /modalidade/i.test(x[0]))) c.splice(1, 0, ['Modalidade', o => { const t = kTipo(o); return t[1] ? kTag(t[0], t[1]) : '—'; }]);
  if(d.lista.some(o => kFin(o) !== '—') && !c.some(x => /^financeiro$/i.test(x[0]))) c.splice(c.findIndex(x => /modalidade/i.test(x[0])) + 1 || 1, 0, ['Financeiro', o => { const f = kFin(o), cor = {EXE:'#1f4e79', RAP:'#8e44ad', 'EXE e RAP':'#16756b'}[f]; return cor ? kTag(f, cor) : `<small>${esc(f)}</small>`; }]);
  return c;
}
// valor do resumo: coluna de valor com o mesmo nome do cartão (senão a última coluna de valor); lê o número já formatado (Bi/Mi/Mil)
function kpiNum(t){ t = String(t||'').replace(/<small[\s\S]*$/i, '').replace(/<[^>]+>/g, ' ').trim(); const m = t.match(/^([−-])?\s*(?:R\$\s*)?([\d.]+(?:,\d+)?)\s*(Bi|Mi|Mil)?\b/); if(!m) return null;
  let v = parseFloat(m[2].replace(/\./g, '').replace(',', '.')); v *= m[3]==='Bi' ? 1e9 : m[3]==='Mi' ? 1e6 : m[3]==='Mil' ? 1e3 : 1; return m[1] ? -v : v; }
function kpiMetrica(d, cols){
  const ehValor = c => c[2] === 'n' && d.lista.slice(0, 20).some(o => /\b(Bi|Mi|Mil)\b|R\$/.test(String(c[1](o))));
  const norm = s => String(s||'').replace(/<[^>]+>/g, '').trim().toLowerCase();
  const vs = cols.filter(ehValor); if(!vs.length) return null;
  const c = vs.find(x => norm(x[0]) === norm(d.tit)) || vs.find(x => norm(d.tit).includes(norm(x[0]))) || vs[vs.length - 1];
  return o => kpiNum(c[1](o)) || 0;
}
(function(){
  const css = document.createElement('style');
  css.textContent = `.kpi-cl{cursor:pointer;transition:transform .12s, box-shadow .12s}.kpi-cl:hover{transform:translateY(-2px);box-shadow:0 8px 20px rgba(20,40,60,.16)}
  .kpi-on{outline:3px solid #2fae5c;outline-offset:-3px}.kpi-box{border:2px solid #2fae5c}.kpi-cab{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;flex-wrap:wrap}
  .kpi-bt{border:1px solid #b9c7d3;background:#fff;color:#1f4e79;font:600 12.5px inherit;font-family:inherit;padding:6px 12px;border-radius:8px;cursor:pointer;margin-left:6px}
  .kpi-fil{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:flex-end;margin:6px 0 10px}.kpi-fil label{display:flex;flex-direction:column;font-size:11px;font-weight:600;color:#33475b;gap:3px}
  .kpi-fil input,.kpi-fil select{font:inherit;font-size:12px;font-weight:400;padding:5px 8px;border:1px solid #cfd8e3;border-radius:6px;background:#f7f9fb;min-width:120px}.kpi-fil input{min-width:170px}
  .kpi-res{margin-left:auto;align-self:center;font-size:12px;background:#eef3f8;border:1px solid #9fb3c8;border-radius:14px;padding:4px 12px;color:#14324f;white-space:nowrap}.kpi-res.fil{background:#fff6e5;border-color:#f0c36d;color:#7a4b00}`;
  document.head.appendChild(css);
  const _render = render;
  render = function(){ _render.apply(this, arguments); try{ kpiDepois(); }catch(e){ console.error(e); } };
  document.addEventListener('click', e => {
    const k = e.target.closest('[data-kpi]');
    if(k){ e.stopImmediatePropagation(); window.__kpi = window.__kpi === k.dataset.kpi ? null : k.dataset.kpi; if(typeof PAG === 'object') PAG.k = 0; kpiDepois();
      const b = document.getElementById('kpLista'); if(b && window.__kpi) b.scrollIntoView({block:'nearest', behavior:'smooth'}); return; }
    if(e.target.closest('[data-kpifecha]')){ e.stopImmediatePropagation(); window.__kpi = null; kpiDepois(); return; }
    if(e.target.closest('[data-kflimpa]')){ e.stopImmediatePropagation(); KF = {__on: window.__kpi}; if(typeof PAG === 'object') PAG.k = 0; kpiDepois(); return; }
    if(e.target.closest('[data-kpicsv]')){ e.stopImmediatePropagation(); const d = (window.KPI_DEF||{})[window.__kpi]; if(!d) return;
      const txt = s => String(s ?? '').replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
      const cs = kpiCols(d), linhas = [cs.map(c => txt(c[0]))].concat(kpiFiltrar(d.lista).map(o => cs.map(c => txt(c[1](o)))));
      const csv = '﻿' + linhas.map(l => l.map(v => '"' + v.replace(/"/g, '""') + '"').join(';')).join('\r\n');
      const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], {type:'text/csv'})); a.download = (d.tit || 'lista').replace(/[^\wÀ-ú ]+/g, '').trim().replace(/\s+/g, '_') + '.csv';
      document.body.appendChild(a); a.click(); a.remove(); return; }
  }, true);
  let tmK; const mudaK = e => { const x = e.target.closest && e.target.closest('[data-kf]'); if(!x) return; e.stopImmediatePropagation();
    KF[x.dataset.kf] = x.value; if(typeof PAG === 'object') PAG.k = 0; clearTimeout(tmK); tmK = setTimeout(kpiDepois, x.type === 'search' ? 250 : 0); };
  document.addEventListener('input', mudaK, true); document.addEventListener('change', mudaK, true);
})();
